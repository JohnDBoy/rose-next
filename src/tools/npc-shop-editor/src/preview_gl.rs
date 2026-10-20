//! Draws a [`Scene`] inside an egui paint callback (eframe's glow backend).
//!
//! egui_glow re-applies its own state after every callback
//! (`Painter::prepare_painting`), but not the depth mask, so that is restored
//! here. The pane needs `NativeOptions::depth_buffer`: without one the depth
//! test passes everything and back faces show through.
//!
//! Vertices are posed on the CPU ([`Scene::pose`]) and streamed into dynamic
//! buffers each paint: a few thousand vertices, cheaper than a skinning shader
//! and the same code the headless renderer uses.

use eframe::egui_glow::ShaderVersion;
use eframe::glow::{self, HasContext};

use crate::preview::{Mat4, Posed, Scene, Vertex, BACKGROUND};

pub struct GlScene {
    program: glow::Program,
    meshes: Vec<GpuMesh>,
    textures: Vec<glow::Texture>,
    /// 1x1 grey, for parts whose texture did not load.
    grey: glow::Texture,
}

struct GpuMesh {
    /// Index into the scene's meshes (empty ones are not uploaded).
    source: usize,
    vao: glow::VertexArray,
    vbo: glow::Buffer,
    ebo: glow::Buffer,
    count: i32,
    texture: Option<usize>,
    /// 0..1, negative for none.
    alpha_ref: f32,
    blend: bool,
}

const VERTEX: &str = r#"
#if NEW_SHADER_INTERFACE
    #define I in
    #define O out
#else
    #define I attribute
    #define O varying
#endif
uniform mat4 u_view_projection;
I vec3 a_position;
I vec3 a_normal;
I vec2 a_uv;
O vec3 v_normal;
O vec2 v_uv;
void main() {
    gl_Position = u_view_projection * vec4(a_position, 1.0);
    v_normal = a_normal;
    v_uv = a_uv;
}
"#;

const FRAGMENT: &str = r#"
#ifdef GL_ES
    precision mediump float;
#endif
#if NEW_SHADER_INTERFACE
    in vec3 v_normal;
    in vec2 v_uv;
    out vec4 f_color;
    #define gl_FragColor f_color
    #define texture2D texture
#else
    varying vec3 v_normal;
    varying vec2 v_uv;
#endif
uniform sampler2D u_texture;
uniform vec3 u_light;
uniform float u_alpha_ref;
uniform float u_blend;
void main() {
    vec4 texel = texture2D(u_texture, v_uv);
    if (u_alpha_ref >= 0.0 && texel.a < u_alpha_ref) {
        discard;
    }
    // Two-sided Lambert plus ambient: preview::shade.
    float shade = 0.5 + 0.65 * abs(dot(normalize(v_normal), u_light));
    gl_FragColor = vec4(min(texel.rgb * shade, vec3(1.0)), mix(1.0, texel.a, u_blend));
}
"#;

impl GlScene {
    pub fn new(gl: &glow::Context) -> Result<Self, String> {
        let version = ShaderVersion::get(gl);
        let header = format!(
            "{}\n#define NEW_SHADER_INTERFACE {}\n",
            version.version_declaration(),
            i32::from(version.is_new_shader_interface())
        );
        unsafe {
            let program = gl.create_program()?;
            let mut shaders = Vec::new();
            for (kind, source) in [
                (glow::VERTEX_SHADER, VERTEX),
                (glow::FRAGMENT_SHADER, FRAGMENT),
            ] {
                let shader = gl.create_shader(kind)?;
                gl.shader_source(shader, &format!("{header}{source}"));
                gl.compile_shader(shader);
                if !gl.get_shader_compile_status(shader) {
                    return Err(gl.get_shader_info_log(shader));
                }
                gl.attach_shader(program, shader);
                shaders.push(shader);
            }
            for (location, name) in ["a_position", "a_normal", "a_uv"].iter().enumerate() {
                gl.bind_attrib_location(program, location as u32, name);
            }
            gl.link_program(program);
            if !gl.get_program_link_status(program) {
                return Err(gl.get_program_info_log(program));
            }
            for shader in shaders {
                gl.detach_shader(program, shader);
                gl.delete_shader(shader);
            }
            let grey = upload_texture(gl, 1, 1, &[150, 150, 150, 255])?;
            Ok(Self {
                program,
                meshes: Vec::new(),
                textures: Vec::new(),
                grey,
            })
        }
    }

    /// Replace whatever was uploaded with `scene`; [`GlScene::paint`] fills the vertices.
    pub fn upload(&mut self, gl: &glow::Context, scene: &Scene) -> Result<(), String> {
        self.clear(gl);
        unsafe {
            for image in &scene.textures {
                let texture = upload_texture(gl, image.width, image.height, &image.rgba)?;
                self.textures.push(texture);
            }
            for (source, mesh) in scene.meshes.iter().enumerate() {
                if mesh.indices.is_empty() {
                    continue;
                }
                let vao = gl.create_vertex_array()?;
                gl.bind_vertex_array(Some(vao));
                let vbo = gl.create_buffer()?;
                gl.bind_buffer(glow::ARRAY_BUFFER, Some(vbo));
                gl.buffer_data_size(
                    glow::ARRAY_BUFFER,
                    (mesh.vertex_count() * std::mem::size_of::<Vertex>()) as i32,
                    glow::DYNAMIC_DRAW,
                );
                let ebo = gl.create_buffer()?;
                gl.bind_buffer(glow::ELEMENT_ARRAY_BUFFER, Some(ebo));
                gl.buffer_data_u8_slice(
                    glow::ELEMENT_ARRAY_BUFFER,
                    as_bytes(&mesh.indices),
                    glow::STATIC_DRAW,
                );
                let stride = std::mem::size_of::<Vertex>() as i32;
                for (location, size, offset) in [(0, 3, 0), (1, 3, 12), (2, 2, 24)] {
                    gl.enable_vertex_attrib_array(location);
                    gl.vertex_attrib_pointer_f32(
                        location,
                        size,
                        glow::FLOAT,
                        false,
                        stride,
                        offset,
                    );
                }
                gl.bind_vertex_array(None);
                self.meshes.push(GpuMesh {
                    source,
                    vao,
                    vbo,
                    ebo,
                    count: mesh.indices.len() as i32,
                    texture: mesh.texture,
                    alpha_ref: mesh.alpha_cutoff().unwrap_or(-1.0),
                    blend: mesh.blended(),
                });
            }
        }
        Ok(())
    }

    /// `posed` is the uploaded scene's [`Scene::pose`]. `scissor` is the pane in
    /// GL pixels (x, y from the bottom, width, height): egui scissors to the
    /// shape's clip rect, which can be the whole window, and the clear below
    /// would wipe every panel drawn before the pane.
    pub fn paint(
        &self,
        gl: &glow::Context,
        posed: &Posed,
        view_projection: &Mat4,
        light: [f32; 3],
        scissor: [i32; 4],
    ) {
        unsafe {
            for mesh in &self.meshes {
                if let Some(vertices) = posed.get(mesh.source) {
                    gl.bind_buffer(glow::ARRAY_BUFFER, Some(mesh.vbo));
                    gl.buffer_sub_data_u8_slice(glow::ARRAY_BUFFER, 0, as_bytes(vertices));
                }
            }
            gl.bind_buffer(glow::ARRAY_BUFFER, None);
            gl.enable(glow::SCISSOR_TEST);
            gl.scissor(scissor[0], scissor[1], scissor[2], scissor[3]);
            gl.clear_color(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], BACKGROUND[3]);
            gl.clear_depth_f32(1.0);
            gl.depth_mask(true);
            gl.clear(glow::COLOR_BUFFER_BIT | glow::DEPTH_BUFFER_BIT);
            gl.enable(glow::DEPTH_TEST);
            gl.depth_func(glow::LEQUAL);
            gl.disable(glow::CULL_FACE);
            gl.use_program(Some(self.program));
            let uniform = |name| gl.get_uniform_location(self.program, name);
            gl.uniform_matrix_4_f32_slice(
                uniform("u_view_projection").as_ref(),
                false,
                &view_projection.0,
            );
            gl.uniform_3_f32(uniform("u_light").as_ref(), light[0], light[1], light[2]);
            gl.uniform_1_i32(uniform("u_texture").as_ref(), 0);
            gl.active_texture(glow::TEXTURE0);
            let alpha_ref = uniform("u_alpha_ref");
            let blend_uniform = uniform("u_blend");
            for blend in [false, true] {
                if blend {
                    gl.enable(glow::BLEND);
                    gl.blend_func(glow::SRC_ALPHA, glow::ONE_MINUS_SRC_ALPHA);
                    gl.depth_mask(false);
                } else {
                    gl.disable(glow::BLEND);
                }
                for mesh in self.meshes.iter().filter(|m| m.blend == blend) {
                    let texture = mesh
                        .texture
                        .and_then(|i| self.textures.get(i))
                        .unwrap_or(&self.grey);
                    gl.bind_texture(glow::TEXTURE_2D, Some(*texture));
                    gl.uniform_1_f32(alpha_ref.as_ref(), mesh.alpha_ref);
                    gl.uniform_1_f32(blend_uniform.as_ref(), if blend { 1.0 } else { 0.0 });
                    gl.bind_vertex_array(Some(mesh.vao));
                    gl.draw_elements(glow::TRIANGLES, mesh.count, glow::UNSIGNED_INT, 0);
                }
            }
            gl.bind_vertex_array(None);
            gl.depth_mask(true);
            gl.disable(glow::DEPTH_TEST);
        }
    }

    fn clear(&mut self, gl: &glow::Context) {
        unsafe {
            for mesh in self.meshes.drain(..) {
                gl.delete_vertex_array(mesh.vao);
                gl.delete_buffer(mesh.vbo);
                gl.delete_buffer(mesh.ebo);
            }
            for texture in self.textures.drain(..) {
                gl.delete_texture(texture);
            }
        }
    }

    pub fn destroy(&mut self, gl: &glow::Context) {
        self.clear(gl);
        unsafe {
            gl.delete_texture(self.grey);
            gl.delete_program(self.program);
        }
    }
}

unsafe fn upload_texture(
    gl: &glow::Context,
    width: u32,
    height: u32,
    rgba: &[u8],
) -> Result<glow::Texture, String> {
    let texture = gl.create_texture()?;
    gl.bind_texture(glow::TEXTURE_2D, Some(texture));
    gl.pixel_store_i32(glow::UNPACK_ALIGNMENT, 1);
    // Row 0 is the top of the DDS, at v = 0: the D3D convention the UVs use.
    gl.tex_image_2d(
        glow::TEXTURE_2D,
        0,
        glow::RGBA8 as i32,
        width as i32,
        height as i32,
        0,
        glow::RGBA,
        glow::UNSIGNED_BYTE,
        Some(rgba),
    );
    gl.generate_mipmap(glow::TEXTURE_2D);
    for (name, value) in [
        (glow::TEXTURE_MIN_FILTER, glow::LINEAR_MIPMAP_LINEAR),
        (glow::TEXTURE_MAG_FILTER, glow::LINEAR),
        (glow::TEXTURE_WRAP_S, glow::REPEAT),
        (glow::TEXTURE_WRAP_T, glow::REPEAT),
    ] {
        gl.tex_parameter_i32(glow::TEXTURE_2D, name, value as i32);
    }
    Ok(texture)
}

fn as_bytes<T: Copy>(items: &[T]) -> &[u8] {
    // Vertex is repr(C) f32s and indices are u32: no padding, no invalid bytes.
    unsafe { std::slice::from_raw_parts(items.as_ptr().cast(), std::mem::size_of_val(items)) }
}
