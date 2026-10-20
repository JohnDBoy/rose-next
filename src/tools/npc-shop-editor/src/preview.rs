//! 3D preview of a wearable item, built the way the client builds an avatar
//! (client source in brackets):
//!
//! - A slot's model is the item number itself, looked up in that slot's part
//!   table for the character's sex [`CObjAVT::Create` -> `SetPartMODEL`; the
//!   tables are listed in `CBasicDATA::Load3DDATA`]. An empty slot is item 0,
//!   which for body, arms and feet is the bare body.
//! - Hair is `hair + HELMET_HAIR_TYPE(cap)` (LIST_CAP column 33): the cut that
//!   fits under that hat.
//! - Body, arms and feet are skinned, and a skinned mesh is stored in the
//!   skeleton's bind pose [`zz_bone`: bone offset = inverse bind world], so
//!   with no animation it is drawn as stored.
//! - Face and hair hang off the head bone; the hat, mask and back item off
//!   skeleton dummies. A part's own bone/dummy tag wins over the slot's
//!   default, and a bone wins over a dummy [`CCharPART::Load`, `Load_ZMODEL`].
//!   Avatar parts ignore their ZSC position, rotation and scale.
//! - ZMD translations are centimetres [`zz_skeleton` scales by ZZ_SCALE_IN];
//!   ZMS 7/8 positions are already metres.
//!
//! Nothing here touches the GPU: `preview_gl` uploads a [`Scene`], and
//! [`render`] rasterises one on the CPU for the headless `--preview` check.

use std::collections::HashMap;
use std::io::Cursor;

use anyhow::{anyhow, Result};
use roselib::files::{ZMD, ZMS};
use roselib::io::RoseFile;

use crate::assets::{normalize, Assets};
use crate::data::ItemCategory;
use crate::dds::{self, DecodedImage};
use crate::monsters::{Zsc, ZscMaterial};
use crate::text::{self, Codec};

/// `BONE_IDX_HEAD`, `DUMMY_IDX_BACK`, `DUMMY_IDX_MOUSE`, `DUMMY_IDX_CAP`
/// (common/shared/datatype.h).
const BONE_HEAD: i16 = 4;
const DUMMY_BACK: i16 = 3;
const DUMMY_MOUTH: i16 = 4;
const DUMMY_CAP: i16 = 6;
/// `HELMET_HAIR_TYPE` (common/include/rose/io/stb.h).
const HELMET_HAIR_TYPE_COLUMN: usize = 33;
/// ZZ_SCALE_IN: skeleton files are in centimetres, meshes in metres.
const SKELETON_SCALE: f32 = 0.01;

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Sex {
    Male,
    Female,
}

impl Sex {
    fn skeleton(self) -> &'static str {
        match self {
            Sex::Male => "3DDATA/AVATAR/MALE.ZMD",
            Sex::Female => "3DDATA/AVATAR/FEMALE.ZMD",
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Slot {
    Face,
    Hair,
    Cap,
    Body,
    Arms,
    Foot,
    FaceItem,
    Back,
}

impl Slot {
    const ALL: [Slot; 8] = [
        Slot::Face,
        Slot::Hair,
        Slot::Cap,
        Slot::Body,
        Slot::Arms,
        Slot::Foot,
        Slot::FaceItem,
        Slot::Back,
    ];

    /// The slot an item category is worn in, if the preview can show it.
    pub fn for_category(category: ItemCategory) -> Option<Slot> {
        Some(match category {
            ItemCategory::Face => Slot::FaceItem,
            ItemCategory::Cap => Slot::Cap,
            ItemCategory::Body => Slot::Body,
            ItemCategory::Arms => Slot::Arms,
            ItemCategory::Foot => Slot::Foot,
            ItemCategory::Back => Slot::Back,
            _ => return None,
        })
    }

    fn label(self) -> &'static str {
        match self {
            Slot::Face => "Face",
            Slot::Hair => "Hair",
            Slot::Cap => "Helmet",
            Slot::Body => "Body",
            Slot::Arms => "Gauntlets",
            Slot::Foot => "Boots",
            Slot::FaceItem => "Face item",
            Slot::Back => "Back",
        }
    }

    fn table(self, sex: Sex) -> &'static str {
        let male = sex == Sex::Male;
        match self {
            Slot::Face if male => "3DDATA/AVATAR/LIST_MFACE.ZSC",
            Slot::Face => "3DDATA/AVATAR/LIST_WFACE.ZSC",
            Slot::Hair if male => "3DDATA/AVATAR/LIST_MHAIR.ZSC",
            Slot::Hair => "3DDATA/AVATAR/LIST_WHAIR.ZSC",
            Slot::Cap if male => "3DDATA/AVATAR/LIST_MCAP.ZSC",
            Slot::Cap => "3DDATA/AVATAR/LIST_WCAP.ZSC",
            Slot::Body if male => "3DDATA/AVATAR/LIST_MBODY.ZSC",
            Slot::Body => "3DDATA/AVATAR/LIST_WBODY.ZSC",
            Slot::Arms if male => "3DDATA/AVATAR/LIST_MARMS.ZSC",
            Slot::Arms => "3DDATA/AVATAR/LIST_WARMS.ZSC",
            Slot::Foot if male => "3DDATA/AVATAR/LIST_MFOOT.ZSC",
            Slot::Foot => "3DDATA/AVATAR/LIST_WFOOT.ZSC",
            // One table for both sexes.
            Slot::FaceItem => "3DDATA/AVATAR/LIST_FACEIEM.ZSC",
            Slot::Back => "3DDATA/AVATAR/LIST_BACK.ZSC",
        }
    }

    /// (bone, dummy) a part links to when its ZSC entry names neither.
    fn default_link(self) -> (i16, i16) {
        match self {
            Slot::Face | Slot::Hair => (BONE_HEAD, -1),
            Slot::Cap => (-1, DUMMY_CAP),
            Slot::FaceItem => (-1, DUMMY_MOUTH),
            Slot::Back => (-1, DUMMY_BACK),
            Slot::Body | Slot::Arms | Slot::Foot => (-1, -1),
        }
    }
}

/// Whether `assets` holds avatar models at all: the tester package ships
/// tables and icons only, and gets no preview rather than a list of misses.
pub fn has_avatar_models(assets: &Assets) -> bool {
    assets.exists(Slot::Body.table(Sex::Male))
}

/// Everything the preview reads once per data folder: the part tables, the two
/// skeletons in bind pose, and each hat's hair type.
pub struct AvatarModels {
    tables: HashMap<&'static str, Result<Zsc, String>>,
    poses: HashMap<Sex, Result<Pose, String>>,
    hair_types: Vec<i32>,
    /// Problems that apply to every preview from this folder.
    pub warnings: Vec<String>,
}

impl AvatarModels {
    pub fn load(assets: &Assets, codec: Codec) -> Self {
        let mut tables = HashMap::new();
        let mut poses = HashMap::new();
        for sex in [Sex::Male, Sex::Female] {
            for slot in Slot::ALL {
                let path = slot.table(sex);
                tables.entry(path).or_insert_with(|| {
                    assets
                        .read(path)
                        .and_then(|bytes| Zsc::parse(&bytes))
                        .map_err(|e| format!("{path}: {e:#}"))
                });
            }
            let pose = assets
                .read(sex.skeleton())
                .and_then(|bytes| {
                    let mut zmd = ZMD::new();
                    zmd.read(&mut Cursor::new(bytes))
                        .map_err(|e| anyhow!("{e}"))?;
                    Ok(Pose::bind(&zmd))
                })
                .map_err(|e| format!("{}: {e:#}", sex.skeleton()));
            poses.insert(sex, pose);
        }
        let mut warnings = Vec::new();
        let hair_types = match assets
            .read("3DDATA/STB/LIST_CAP.STB")
            .and_then(|bytes| text::read_stb(&bytes, codec))
        {
            // The reader keeps the root column, so table column N is cell N + 1.
            Ok(rows) => rows
                .iter()
                .map(|row| {
                    row.get(HELMET_HAIR_TYPE_COLUMN + 1)
                        .and_then(|cell| cell.trim().parse().ok())
                        .unwrap_or(0)
                })
                .collect(),
            Err(e) => {
                warnings.push(format!("Hats keep the full haircut: LIST_CAP.STB: {e:#}"));
                Vec::new()
            }
        };
        Self {
            tables,
            poses,
            hair_types,
            warnings,
        }
    }

    fn table(&self, slot: Slot, sex: Sex) -> Result<&Zsc, &str> {
        match &self.tables[slot.table(sex)] {
            Ok(zsc) => Ok(zsc),
            Err(e) => Err(e),
        }
    }

    /// The first model in `slot` from `start`, stepping by `step`, that has any parts.
    fn first_model(&self, slot: Slot, sex: Sex, start: usize, step: usize) -> i32 {
        self.table(slot, sex)
            .ok()
            .and_then(|zsc| {
                (start..zsc.objects.len())
                    .step_by(step)
                    .find(|&i| !zsc.objects[i].parts.is_empty())
            })
            .map_or(0, |i| i as i32)
    }

    /// A bare character of `sex` wearing only the item `(category, id)`.
    /// `None` when the category is not worn on the body.
    pub fn outfit(&self, sex: Sex, category: ItemCategory, id: i32) -> Option<Outfit> {
        let slot = Slot::for_category(category)?;
        // Character creation (SCRIPTS/SYSTEMFUNC.LUA) offers faces from 1 and
        // hair 0, 5, 10... (each followed by its cuts for the hat types); take
        // the first of each that has a model.
        let mut parts = vec![
            (Slot::Face, self.first_model(Slot::Face, sex, 1, 1)),
            (Slot::Hair, self.first_model(Slot::Hair, sex, 0, 5)),
            (Slot::Body, 0),
            (Slot::Arms, 0),
            (Slot::Foot, 0),
        ];
        match parts.iter_mut().find(|(s, _)| *s == slot) {
            Some(part) => part.1 = id,
            None => parts.push((slot, id)),
        }
        if slot == Slot::Cap {
            let hair_type = self.hair_types.get(id as usize).copied().unwrap_or(0);
            parts[1].1 += hair_type.max(0);
        }
        Some(Outfit {
            sex,
            item: slot,
            parts,
        })
    }

    pub fn build(&self, assets: &Assets, outfit: &Outfit) -> Scene {
        let mut scene = Scene::default();
        let pose = match &self.poses[&outfit.sex] {
            Ok(pose) => Some(pose),
            Err(e) => {
                scene
                    .notes
                    .push(format!("Skeleton unavailable, face and hats float: {e}"));
                None
            }
        };
        let mut textures: HashMap<String, Option<usize>> = HashMap::new();
        let mut item_meshes = Vec::new();
        for &(slot, index) in &outfit.parts {
            let label = slot.label();
            let file = slot
                .table(outfit.sex)
                .rsplit('/')
                .next()
                .unwrap_or_default();
            let zsc = match self.table(slot, outfit.sex) {
                Ok(zsc) => zsc,
                Err(e) => {
                    scene.notes.push(format!("{label}: {e}"));
                    continue;
                }
            };
            let Some(object) = usize::try_from(index).ok().and_then(|i| zsc.objects.get(i)) else {
                scene.notes.push(format!(
                    "{label}: model {index} is outside {file} ({} models)",
                    zsc.objects.len()
                ));
                continue;
            };
            if object.parts.is_empty() && slot == outfit.item {
                scene
                    .notes
                    .push(format!("{label}: model {index} of {file} is empty"));
            }
            for part in &object.parts {
                let mesh_path = usize::try_from(part.mesh)
                    .ok()
                    .and_then(|i| zsc.meshes.get(i));
                let Some(mesh_path) = mesh_path else {
                    scene
                        .notes
                        .push(format!("{label}: mesh {} is outside {file}", part.mesh));
                    continue;
                };
                let mesh = match load_mesh(assets, mesh_path) {
                    Ok(mesh) => mesh,
                    Err(e) => {
                        scene.notes.push(format!("{label}: {mesh_path}: {e:#}"));
                        continue;
                    }
                };
                let (default_bone, default_dummy) = slot.default_link();
                let bone = if part.bone >= 0 {
                    part.bone
                } else {
                    default_bone
                };
                let dummy = if part.dummy >= 0 {
                    part.dummy
                } else {
                    default_dummy
                };
                let link = if bone >= 0 {
                    pose.and_then(|p| p.bones.get(bone as usize))
                } else if dummy >= 0 {
                    pose.and_then(|p| p.dummies.get(dummy as usize))
                } else {
                    Some(&IDENTITY)
                };
                let link = link.copied().unwrap_or_else(|| {
                    if pose.is_some() {
                        scene.notes.push(format!(
                            "{label}: the skeleton has no bone {bone} / dummy {dummy}"
                        ));
                    }
                    IDENTITY
                });
                let material = usize::try_from(part.material).ok();
                let flags = material
                    .and_then(|i| zsc.material_flags.get(i))
                    .copied()
                    .unwrap_or_default();
                let texture =
                    match material.and_then(|i| zsc.materials.get(i)) {
                        Some(path) => *textures.entry(normalize(path)).or_insert_with(|| {
                            match assets.read(&normalize(path)).and_then(|b| dds::decode(&b)) {
                                Ok(image) => {
                                    scene.textures.push(image);
                                    Some(scene.textures.len() - 1)
                                }
                                Err(e) => {
                                    scene.notes.push(format!("{label}: {path}: {e:#}"));
                                    None
                                }
                            }
                        }),
                        None => {
                            scene.notes.push(format!(
                                "{label}: material {} is outside {file}",
                                part.material
                            ));
                            None
                        }
                    };
                scene.meshes.push(scene_mesh(&mesh, &link, texture, flags));
                if slot == outfit.item {
                    item_meshes.push(scene.meshes.len() - 1);
                }
            }
        }
        scene.fit(&item_meshes);
        scene
    }
}

/// Which model each slot shows.
#[derive(Clone, PartialEq, Debug)]
pub struct Outfit {
    pub sex: Sex,
    /// The slot of the item being previewed; problems elsewhere are context.
    item: Slot,
    parts: Vec<(Slot, i32)>,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct Vertex {
    pub position: [f32; 3],
    pub normal: [f32; 3],
    pub uv: [f32; 2],
}

pub struct SceneMesh {
    pub vertices: Vec<Vertex>,
    pub indices: Vec<u32>,
    /// Index into [`Scene::textures`]; `None` draws flat grey.
    pub texture: Option<usize>,
    pub material: ZscMaterial,
}

impl SceneMesh {
    /// Alpha-tested parts (hair, fringes) draw as cut-outs with depth; the
    /// engine blends them too, but blending without sorting only adds artefacts.
    /// 0..1, `None` for no test.
    pub fn alpha_cutoff(&self) -> Option<f32> {
        let m = &self.material;
        (m.uses_texture_alpha() && m.alpha_test)
            .then(|| f32::from(m.alpha_ref.clamp(0, 255)) / 255.0)
    }

    /// Texture-alpha parts without a test, drawn after the rest, blended.
    pub fn blended(&self) -> bool {
        self.material.uses_texture_alpha() && !self.material.alpha_test
    }
}

#[derive(Default)]
pub struct Scene {
    pub meshes: Vec<SceneMesh>,
    pub textures: Vec<DecodedImage>,
    pub min: [f32; 3],
    pub max: [f32; 3],
    /// Centre of the previewed item, which the camera closes in on as it zooms.
    pub focus: [f32; 3],
    /// Missing files and other problems, for the panel to list.
    pub notes: Vec<String>,
}

impl Scene {
    fn fit(&mut self, item_meshes: &[usize]) {
        let bounds = |meshes: &mut dyn Iterator<Item = &SceneMesh>| {
            let mut min = [f32::MAX; 3];
            let mut max = [f32::MIN; 3];
            for vertex in meshes.flat_map(|m| &m.vertices) {
                for axis in 0..3 {
                    min[axis] = min[axis].min(vertex.position[axis]);
                    max[axis] = max[axis].max(vertex.position[axis]);
                }
            }
            (min[0] <= max[0]).then_some((min, max))
        };
        let (min, max) =
            bounds(&mut self.meshes.iter()).unwrap_or(([-0.5, -0.5, 0.0], [0.5, 0.5, 1.8]));
        (self.min, self.max) = (min, max);
        let (lo, hi) =
            bounds(&mut item_meshes.iter().map(|&i| &self.meshes[i])).unwrap_or((min, max));
        self.focus = [0, 1, 2].map(|a| (lo[a] + hi[a]) * 0.5);
    }

    pub fn triangles(&self) -> usize {
        self.meshes.iter().map(|m| m.indices.len() / 3).sum()
    }
}

fn load_mesh(assets: &Assets, path: &str) -> Result<ZMS> {
    let bytes = assets.read(&normalize(path))?;
    let mut mesh = ZMS::new();
    mesh.read(&mut Cursor::new(bytes))
        .map_err(|e| anyhow!("{e}"))?;
    Ok(mesh)
}

/// The mesh moved to where its bone or dummy holds it, ready to draw.
fn scene_mesh(mesh: &ZMS, link: &Mat4, texture: Option<usize>, material: ZscMaterial) -> SceneMesh {
    let count = mesh.vertices.len();
    let indices: Vec<u32> = mesh
        .indices
        .iter()
        // Counts are u16 in the engine; roselib reads them as i16.
        .flat_map(|t| [t.x as u16 as u32, t.y as u16 as u32, t.z as u16 as u32])
        .collect();
    let indices: Vec<u32> = indices
        .chunks_exact(3)
        .filter(|t| t.iter().all(|&i| (i as usize) < count))
        .flatten()
        .copied()
        .collect();
    let mut normals: Vec<[f32; 3]> = mesh
        .vertices
        .iter()
        .map(|v| [v.normal.x, v.normal.y, v.normal.z])
        .collect();
    if !mesh.normals_enabled() {
        normals = smooth_normals(mesh, &indices);
    }
    let vertices = mesh
        .vertices
        .iter()
        .zip(normals)
        .map(|(v, n)| Vertex {
            position: link.point([v.position.x, v.position.y, v.position.z]),
            normal: normalized(link.direction(n)),
            uv: [v.uv1.x, v.uv1.y],
        })
        .collect();
    SceneMesh {
        vertices,
        indices,
        texture,
        material,
    }
}

fn smooth_normals(mesh: &ZMS, indices: &[u32]) -> Vec<[f32; 3]> {
    let pos = |i: u32| {
        let p = &mesh.vertices[i as usize].position;
        [p.x, p.y, p.z]
    };
    let mut normals = vec![[0.0; 3]; mesh.vertices.len()];
    for t in indices.chunks_exact(3) {
        let n = cross(sub(pos(t[1]), pos(t[0])), sub(pos(t[2]), pos(t[0])));
        for &i in t {
            for axis in 0..3 {
                normals[i as usize][axis] += n[axis];
            }
        }
    }
    normals.into_iter().map(normalized).collect()
}

/// World transforms of a skeleton's bones and dummies in its bind pose.
struct Pose {
    bones: Vec<Mat4>,
    dummies: Vec<Mat4>,
}

impl Pose {
    fn bind(zmd: &ZMD) -> Self {
        let local = |bone: &roselib::files::zmd::Bone| {
            let p = &bone.position;
            let q = &bone.rotation;
            Mat4::translation([p.x, p.y, p.z].map(|c| c * SKELETON_SCALE))
                .mul(&Mat4::rotation(q.w, q.x, q.y, q.z))
        };
        let count = zmd.bones.len();
        let mut world: Vec<Option<Mat4>> = vec![None; count];
        // Parents usually come first, but nothing promises it: resolve until
        // nothing changes, then let anything left (a cycle) stand on its own.
        loop {
            let mut changed = false;
            for (i, bone) in zmd.bones.iter().enumerate() {
                if world[i].is_some() {
                    continue;
                }
                let parent = usize::try_from(bone.parent)
                    .ok()
                    .filter(|&p| p < count && p != i);
                let resolved = match parent {
                    None => Some(local(bone)),
                    Some(p) => world[p].map(|parent| parent.mul(&local(bone))),
                };
                if resolved.is_some() {
                    world[i] = resolved;
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
        let bones: Vec<Mat4> = world
            .iter()
            .zip(&zmd.bones)
            .map(|(w, bone)| w.unwrap_or_else(|| local(bone)))
            .collect();
        let dummies = zmd
            .dummy_bones
            .iter()
            .map(|dummy| {
                let parent = usize::try_from(dummy.parent)
                    .ok()
                    .and_then(|p| bones.get(p))
                    .copied()
                    .unwrap_or(IDENTITY);
                parent.mul(&local(dummy))
            })
            .collect();
        Self { bones, dummies }
    }
}

/// Orbit camera around the scene's bounds.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Camera {
    /// Radians around the vertical axis; 0 looks at the character's face.
    pub yaw: f32,
    pub pitch: f32,
    /// 1 frames the whole scene; smaller is closer.
    pub zoom: f32,
}

impl Default for Camera {
    fn default() -> Self {
        Self {
            yaw: 0.0,
            pitch: 0.12,
            zoom: 1.0,
        }
    }
}

const FIELD_OF_VIEW: f32 = 0.6;
/// Closest zoom the pane allows.
pub const MIN_ZOOM: f32 = 0.2;

impl Camera {
    /// (view-projection, light direction toward the light) for a viewport of `aspect` = w / h.
    pub fn matrices(&self, scene: &Scene, aspect: f32) -> (Mat4, [f32; 3]) {
        // Whole figure at zoom 1, the item itself by the closest zoom.
        let t = ((1.0 - self.zoom) / (1.0 - MIN_ZOOM)).clamp(0.0, 1.0);
        let center = [0, 1, 2].map(|a| {
            let middle = (scene.min[a] + scene.max[a]) * 0.5;
            middle + (scene.focus[a] - middle) * t
        });
        let radius = (0..3)
            .map(|a| (scene.max[a] - scene.min[a]) * 0.5)
            .map(|h| h * h)
            .sum::<f32>()
            .sqrt()
            .max(0.05);
        // Fit the box: its footprint at any heading across, its height up.
        // A sphere would be set by the T-pose's arm span and leave the figure small.
        let across = 0.5 * (scene.max[0] - scene.min[0]).hypot(scene.max[1] - scene.min[1]);
        let up = 0.5 * (scene.max[2] - scene.min[2]);
        let tan_up = (FIELD_OF_VIEW * 0.5).tan();
        let fit = (across / (tan_up * aspect)).max(up / tan_up) * 1.1 + across;
        let distance = fit.max(0.1) * self.zoom;
        // The avatar faces -Y in its own space.
        let yaw = self.yaw - std::f32::consts::FRAC_PI_2;
        let direction = [
            self.pitch.cos() * yaw.cos(),
            self.pitch.cos() * yaw.sin(),
            self.pitch.sin(),
        ];
        let eye = [0, 1, 2].map(|a| center[a] + direction[a] * distance);
        let view = Mat4::look_at(eye, center, [0.0, 0.0, 1.0]);
        let near = (distance - radius * 1.5).max(distance * 0.02);
        // The orbit centre can sit a radius off the middle when zoomed onto the item.
        let far = distance + radius * 2.5;
        let projection = Mat4::perspective(FIELD_OF_VIEW, aspect, near, far);
        // Key light from above, front and a little to the side of the camera.
        let side = [-direction[1], direction[0], 0.0];
        let light = normalized([0, 1, 2].map(|a| direction[a] + side[a] * 0.4));
        let light = normalized([light[0], light[1], light[2] + 0.6]);
        (projection.mul(&view), light)
    }
}

/// Rasterise `scene` on the CPU into RGBA8 the way the GL pane draws it.
/// Used by the headless `--preview` check, never by the window.
pub fn render(scene: &Scene, camera: &Camera, width: usize, height: usize) -> Vec<u8> {
    let (view_projection, light) = camera.matrices(scene, width as f32 / height as f32);
    let mut color = vec![0u8; width * height * 4];
    for pixel in color.chunks_exact_mut(4) {
        pixel.copy_from_slice(&BACKGROUND.map(|c| (c * 255.0) as u8));
    }
    let mut depth = vec![f32::MAX; width * height];
    for blended in [false, true] {
        for mesh in scene.meshes.iter().filter(|m| m.blended() == blended) {
            let texture = mesh.texture.map(|i| &scene.textures[i]);
            let clip: Vec<[f32; 4]> = mesh
                .vertices
                .iter()
                .map(|v| view_projection.project(v.position))
                .collect();
            for t in mesh.indices.chunks_exact(3) {
                let [a, b, c] = [t[0], t[1], t[2]].map(|i| i as usize);
                if [a, b, c].iter().any(|&i| clip[i][3] <= 1e-4) {
                    continue;
                }
                let screen = [a, b, c].map(|i| {
                    let [x, y, z, w] = clip[i];
                    [
                        (x / w + 1.0) * 0.5 * width as f32,
                        (1.0 - y / w) * 0.5 * height as f32,
                        z / w,
                        1.0 / w,
                    ]
                });
                let area = edge(screen[0], screen[1], screen[2]);
                if area.abs() < 1e-9 {
                    continue;
                }
                let lo = |axis: usize| screen.iter().map(|s| s[axis]).fold(f32::MAX, f32::min);
                let hi = |axis: usize| screen.iter().map(|s| s[axis]).fold(f32::MIN, f32::max);
                let x0 = lo(0).floor().max(0.0) as usize;
                let x1 = (hi(0).ceil() as usize).min(width);
                let y0 = lo(1).floor().max(0.0) as usize;
                let y1 = (hi(1).ceil() as usize).min(height);
                for y in y0..y1 {
                    for x in x0..x1 {
                        let p = [x as f32 + 0.5, y as f32 + 0.5, 0.0, 0.0];
                        let w = [
                            edge(screen[1], screen[2], p) / area,
                            edge(screen[2], screen[0], p) / area,
                            edge(screen[0], screen[1], p) / area,
                        ];
                        if w.iter().any(|&w| w < 0.0) {
                            continue;
                        }
                        let z = w[0] * screen[0][2] + w[1] * screen[1][2] + w[2] * screen[2][2];
                        let at = y * width + x;
                        if !(-1.0..=1.0).contains(&z) || z >= depth[at] {
                            continue;
                        }
                        // Perspective-correct attributes.
                        let inv = [0, 1, 2].map(|k| w[k] * screen[k][3]);
                        let sum: f32 = inv.iter().sum();
                        let vs = [a, b, c].map(|i| &mesh.vertices[i]);
                        let mix2 = |f: &dyn Fn(&Vertex) -> f32| {
                            (0..3).map(|k| inv[k] * f(vs[k])).sum::<f32>() / sum
                        };
                        let uv = [mix2(&|v| v.uv[0]), mix2(&|v| v.uv[1])];
                        let normal = [0, 1, 2].map(|axis| mix2(&|v| v.normal[axis]));
                        let texel = texture.map_or([0.6, 0.6, 0.6, 1.0], |t| sample(t, uv));
                        if mesh.alpha_cutoff().is_some_and(|cutoff| texel[3] < cutoff) {
                            continue;
                        }
                        let shade = shade(normalized(normal), light);
                        let alpha = if blended { texel[3] } else { 1.0 };
                        let out = &mut color[at * 4..at * 4 + 4];
                        for k in 0..3 {
                            let lit = (texel[k] * shade).min(1.0) * 255.0;
                            out[k] = (lit * alpha + f32::from(out[k]) * (1.0 - alpha)) as u8;
                        }
                        if !blended {
                            depth[at] = z;
                        }
                    }
                }
            }
        }
    }
    color
}

/// Clear colour of the pane, linear 0..1.
pub const BACKGROUND: [f32; 4] = [0.11, 0.12, 0.14, 1.0];

/// Two-sided Lambert plus ambient; `preview_gl`'s fragment shader matches it.
fn shade(normal: [f32; 3], light: [f32; 3]) -> f32 {
    0.5 + 0.65 * dot(normal, light).abs()
}

fn sample(texture: &DecodedImage, uv: [f32; 2]) -> [f32; 4] {
    let wrap = |c: f32, size: u32| ((c - c.floor()) * size as f32) as u32 % size.max(1);
    let x = wrap(uv[0], texture.width);
    let y = wrap(uv[1], texture.height);
    let at = ((y * texture.width + x) * 4) as usize;
    let p = &texture.rgba[at..at + 4];
    [0, 1, 2, 3].map(|k| f32::from(p[k]) / 255.0)
}

fn edge(a: [f32; 4], b: [f32; 4], p: [f32; 4]) -> f32 {
    (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
}

fn sub(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

fn cross(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn dot(a: [f32; 3], b: [f32; 3]) -> f32 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

fn normalized(v: [f32; 3]) -> [f32; 3] {
    let length = dot(v, v).sqrt();
    if length < 1e-12 {
        [0.0, 0.0, 1.0]
    } else {
        v.map(|c| c / length)
    }
}

/// Column-major 4x4 matrix, the layout GL uniforms take.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Mat4(pub [f32; 16]);

const IDENTITY: Mat4 = Mat4([
    1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0,
]);

impl Mat4 {
    fn at(&self, row: usize, col: usize) -> f32 {
        self.0[col * 4 + row]
    }

    fn mul(&self, other: &Mat4) -> Mat4 {
        let mut out = [0.0; 16];
        for col in 0..4 {
            for row in 0..4 {
                out[col * 4 + row] = (0..4).map(|k| self.at(row, k) * other.at(k, col)).sum();
            }
        }
        Mat4(out)
    }

    fn translation(t: [f32; 3]) -> Mat4 {
        let mut m = IDENTITY;
        m.0[12..15].copy_from_slice(&t);
        m
    }

    /// A unit quaternion's rotation. A zero quaternion (ZMD0002 dummies carry
    /// no rotation) is the identity.
    fn rotation(w: f32, x: f32, y: f32, z: f32) -> Mat4 {
        let length = (w * w + x * x + y * y + z * z).sqrt();
        if length < 1e-6 {
            return IDENTITY;
        }
        let (w, x, y, z) = (w / length, x / length, y / length, z / length);
        Mat4([
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y + w * z),
            2.0 * (x * z - w * y),
            0.0,
            2.0 * (x * y - w * z),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z + w * x),
            0.0,
            2.0 * (x * z + w * y),
            2.0 * (y * z - w * x),
            1.0 - 2.0 * (x * x + y * y),
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ])
    }

    fn look_at(eye: [f32; 3], target: [f32; 3], up: [f32; 3]) -> Mat4 {
        let f = normalized(sub(target, eye));
        let s = normalized(cross(f, up));
        let u = cross(s, f);
        Mat4([
            s[0],
            u[0],
            -f[0],
            0.0,
            s[1],
            u[1],
            -f[1],
            0.0,
            s[2],
            u[2],
            -f[2],
            0.0,
            -dot(s, eye),
            -dot(u, eye),
            dot(f, eye),
            1.0,
        ])
    }

    /// Right-handed, depth -1..1 (GL).
    fn perspective(fov_y: f32, aspect: f32, near: f32, far: f32) -> Mat4 {
        let f = 1.0 / (fov_y * 0.5).tan();
        let mut m = [0.0; 16];
        m[0] = f / aspect;
        m[5] = f;
        m[10] = (far + near) / (near - far);
        m[11] = -1.0;
        m[14] = 2.0 * far * near / (near - far);
        Mat4(m)
    }

    fn point(&self, p: [f32; 3]) -> [f32; 3] {
        [0, 1, 2].map(|r| {
            self.at(r, 0) * p[0] + self.at(r, 1) * p[1] + self.at(r, 2) * p[2] + self.at(r, 3)
        })
    }

    fn direction(&self, d: [f32; 3]) -> [f32; 3] {
        [0, 1, 2].map(|r| self.at(r, 0) * d[0] + self.at(r, 1) * d[1] + self.at(r, 2) * d[2])
    }

    fn project(&self, p: [f32; 3]) -> [f32; 4] {
        [0, 1, 2, 3].map(|r| {
            self.at(r, 0) * p[0] + self.at(r, 1) * p[1] + self.at(r, 2) * p[2] + self.at(r, 3)
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quaternion_rotates_like_the_engine() {
        // 90 degrees about Z takes +X to +Y.
        let half = std::f32::consts::FRAC_PI_4;
        let m = Mat4::rotation(half.cos(), 0.0, 0.0, half.sin());
        let p = m.point([1.0, 0.0, 0.0]);
        assert!((p[0]).abs() < 1e-6 && (p[1] - 1.0).abs() < 1e-6, "{p:?}");
    }

    #[test]
    fn child_transform_applies_parent_first() {
        let parent = Mat4::translation([1.0, 0.0, 0.0]);
        let half = std::f32::consts::FRAC_PI_4;
        let child = Mat4::rotation(half.cos(), 0.0, 0.0, half.sin());
        let p = parent.mul(&child).point([1.0, 0.0, 0.0]);
        assert!(
            (p[0] - 1.0).abs() < 1e-6 && (p[1] - 1.0).abs() < 1e-6,
            "{p:?}"
        );
    }

    #[test]
    fn camera_frames_the_scene() {
        let scene = Scene {
            min: [-0.5, -0.3, 0.0],
            max: [0.5, 0.3, 1.8],
            ..Default::default()
        };
        let (vp, _) = Camera::default().matrices(&scene, 0.75);
        for corner in [[-0.5, -0.3, 0.0], [0.5, 0.3, 1.8], [0.5, -0.3, 1.8]] {
            let [x, y, z, w] = vp.project(corner);
            assert!(w > 0.0);
            for c in [x / w, y / w, z / w] {
                assert!((-1.0..=1.0).contains(&c), "{corner:?} -> {c}");
            }
        }
    }
}
