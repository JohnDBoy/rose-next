/**
 * @file zz_terrain_batch.cpp
 * @brief One map cell's terrain drawn as a few large draws. See zz_terrain_batch.h.
 */

#include "zz_tier0.h"
#include "zz_algebra.h"
#include "zz_terrain_batch.h"
#include "zz_terrain_block.h"
#include "zz_mesh_tool.h"
#include "zz_render_state.h"
#include "zz_material.h"
#include "zz_light.h"
#include "zz_renderer.h"
#include "zz_system.h"
#include "zz_bvolume.h"
#include "zz_log.h"

ZZ_IMPLEMENT_DYNCREATE(zz_mesh_terrain_batch, zz_mesh)
ZZ_IMPLEMENT_DYNCREATE(zz_terrain_batch, zz_visible)

//--------------------------------------------------------------------------------
zz_mesh_terrain_batch::zz_mesh_terrain_batch () :
	detail_level(0),
	mapsize(0),
	blocksize(0),
	zz_mesh(true)
{
	index_type = zz_mesh::TYPE_LIST;
}

zz_mesh_terrain_batch::~zz_mesh_terrain_batch ()
{
}

/// Per patch, the vertices and faces of zz_mesh_tool::load_terrain_mesh, offset
/// into the shared buffers. The UV math is copied rather than factored out so the
/// per-patch path (still used for picking and with batching off) is untouched;
/// keep the two in step.
bool zz_mesh_terrain_batch::load_mesh ()
{
	const int num_patches = (int)patches.size();
	if (num_patches == 0 || detail_level <= 0) return false;

	set_vertex_format(ZZ_VERTEX_FORMAT_TERRAIN);

	const int vwidth = detail_level + 1;
	const int fwidth = detail_level;
	const int nverts = verts_per_patch();
	const int nfaces = faces_per_patch();

	set_num_verts((uint16)(num_patches * nverts));

	const float unit = blocksize / detail_level;
	const int iunit = int(unit * ZZ_SCALE_OUT);
	const int imapsize = int(mapsize * ZZ_SCALE_OUT);

	vec3 pos;
	vec2 uv;
	int i = 0;

	for (int p = 0; p < num_patches; ++p) {
		const patch_desc& pd = patches[p];
		const int iorig_x = int(pd.orig_x * ZZ_SCALE_OUT);
		const int iorig_y = int(pd.orig_y * ZZ_SCALE_OUT);

		for (int iy = 0; iy < vwidth; iy++) {
			for (int ix = 0; ix < vwidth; ix++) {
				pos.x = pd.orig_x + ix * unit;
				pos.y = pd.orig_y - iy * unit; // x-z plane to x-y plane
				pos.z = pd.heights[iy * vwidth + ix];
				set_pos((uint16)i, pos);

				uv = zz_mesh_tool::get_uv_by_type(fwidth, ix, iy, zz_mesh_tool::zz_uv_type(pd.uv_type0));
				set_uv((uint16)i, 0, uv);

				uv = zz_mesh_tool::get_uv_by_type(fwidth, ix, iy, zz_mesh_tool::zz_uv_type(pd.uv_type1));
				set_uv((uint16)i, 1, uv);

				// light map channel
				if (pd.orig_x < 0) { // negative coordinates
					uv.x = float(iorig_x % (imapsize + 1)) + ix * unit;
					uv.x /= imapsize;
					uv.x += 1.0f;
				}
				else {
					uv.x = float(iorig_x % imapsize) + ix * iunit;
					uv.x /= imapsize;
				}
				if ((pd.orig_y - blocksize) < 0) { // negative coordinates
					uv.y = float(iorig_y % imapsize) - iy * iunit;
					uv.y /= imapsize;
					uv.y += 1.0f;
				}
				else {
					uv.y = float(iorig_y % (imapsize + 1)) - iy * iunit;
					uv.y /= imapsize;
				}
				uv.y = 1.0f - uv.y; // for d3d texture coordinate
				set_uv((uint16)i, 2, uv);

				i++;
			}
		}
	}

	// Faces: the same two triangles per grid square as load_terrain_mesh, shifted to
	// each patch's first vertex -- but both wound clockwise seen from above, the
	// terrain's front face (zz_material_terrain::begin culls CCW). load_terrain_mesh's
	// own face list alternates (its upper face is counter-clockwise) because patches
	// are drawn as the shared triangle strips, where D3D flips every other triangle;
	// that list only serves picking. Drawn as a list, the upper faces were culled and
	// half the ground showed the clear colour through.
	set_num_faces((uint16)(num_patches * nfaces));
	usvec3 indices;
	int f = 0;
	for (int p = 0; p < num_patches; ++p) {
		const int base = p * nverts;
		for (int iy = 0; iy < fwidth; ++iy) {
			for (int ix = 0; ix < fwidth; ++ix) {
				// lower face: (x, y+1), (x, y), (x+1, y+1)
				indices.x = (uint16)(base + ix + (iy + 1) * vwidth);
				indices.y = (uint16)(base + ix + iy * vwidth);
				indices.z = (uint16)(base + (ix + 1) + (iy + 1) * vwidth);
				set_face((uint16)f++, indices);

				// upper face: (x, y), (x+1, y), (x+1, y+1)
				indices.x = (uint16)(base + ix + iy * vwidth);
				indices.y = (uint16)(base + (ix + 1) + iy * vwidth);
				indices.z = (uint16)(base + (ix + 1) + (iy + 1) * vwidth);
				set_face((uint16)f++, indices);
			}
		}
	}

	return true;
}

//--------------------------------------------------------------------------------
zz_terrain_batch::zz_terrain_batch () :
	batch_mesh(NULL)
{
	cast_shadow = false;
	receive_shadow = true;
	receive_fog = true;
	// Picking and collision stay on the patch blocks.
	collision_level = ZZ_CL_NONE;
	draw_priority = ZZ_DP_HIGHEST;
	bv_type = ZZ_BV_OBB;
}

zz_terrain_batch::~zz_terrain_batch ()
{
}

void zz_terrain_batch::add_group (zz_material * material, zz_light * light,
	unsigned int start_face, unsigned int num_faces,
	unsigned int min_vertex, unsigned int num_vertices)
{
	group g;
	g.start_face = start_face;
	g.num_faces = num_faces;
	g.min_vertex = min_vertex;
	g.num_vertices = num_vertices;
	groups.push_back(g);
	zz_visible::add_runit(batch_mesh, material, light);
}

void zz_terrain_batch::render (bool recursive)
{
	zz_assert(batch_mesh);
	if (!batch_mesh) return;

	zz_renderer * r = znzin->renderer;

	if (zz_terrain_block::first_render) {
		mat4 modelview_worldTM;
		get_modelview_worldTM(modelview_worldTM);
		r->set_modelview_matrix(modelview_worldTM);
		r->set_world_matrix(get_worldTM());
		if (num_runits > 0) r->set_light(runits[0].light);
		zz_terrain_block::first_render = false;
	}

	if (!batch_mesh->get_device_updated()) return; // before_render flushes it

	for (unsigned int i = 0; i < groups.size() && i < num_runits; ++i) {
		zz_material * mat = runits[i].material;
		if (!mat) continue;
		mat->set_receive_fog(receive_fog_now);
		mat->set_receive_shadow(receive_shadow_now);
		if (!mat->get_device_updated()) continue;
		const group& g = groups[i];
		r->render_range(batch_mesh, mat, NULL, g.start_face, g.num_faces, g.min_vertex, g.num_vertices);
	}
}

const vec3& zz_terrain_batch::get_com_position_world ()
{
	if (tm_cache_flag & TRANSFORM_CACHE_INDEX_COM_POSITION_WORLD) {
		return com_position_world;
	}
	tm_cache_flag |= TRANSFORM_CACHE_INDEX_COM_POSITION_WORLD;
	com_position_world = get_bvolume()->get_sphere()->center;
	return com_position_world;
}

void zz_terrain_batch::update_bvolume (void)
{
	assert(valid_bvolume);
}

/// Built once, from the cell bounds the client set on the mesh. add_runit calls
/// this for every group; only the first one does anything.
void zz_terrain_batch::reset_bvolume (void)
{
	if (valid_bvolume) return;
	if (!batch_mesh) return;

	minmax[0] = batch_mesh->get_min();
	minmax[1] = batch_mesh->get_max();

	assert(!bv);
	bv = zz_new zz_bvolume();
	bv->set_obb(.5f * (minmax[0] + minmax[1]), .5f * (minmax[1] - minmax[0]));

	valid_bvolume = true;
	scene_refresh();
}

void zz_terrain_batch::update_time (bool recursive, zz_time diff_time)
{
	infrustum = false;
}

void zz_terrain_batch::insert_scene ()
{
	inscene = true;
	scene_refresh();
}

void zz_terrain_batch::remove_scene ()
{
	inscene = false;
	scene_refresh();
}

/// Same as zz_terrain_block: build the device objects now rather than miss a frame.
/// One mesh per cell, so this is one vertex buffer when a cell first comes into view.
void zz_terrain_batch::before_render ()
{
	for (unsigned int i = 0; i < num_runits; ++i) {
		if (runits[i].material) runits[i].material->flush_device(true /* immediate */);
	}
	if (batch_mesh && !batch_mesh->get_device_updated()) {
		batch_mesh->flush_device(true /* immediate */);
	}
}

void zz_terrain_batch::after_render ()
{
}
