/**
 * @file zz_terrain_batch.h
 * @brief One map cell's terrain drawn as a few large draws instead of one per patch.
 *
 * The client builds one terrain block per 10 m patch, so a 160 m map cell is 256
 * blocks, each with its own vertex buffer, material and draw call. With the 5x5
 * map window that was ~5,600 terrain draws a frame on the Far view (7-9 ms of CPU
 * submission), plus 256 small vertex buffers built per newly loaded cell.
 *
 * A batch holds the whole cell in one vertex/index buffer -- the same vertices and
 * UVs zz_mesh_tool::load_terrain_mesh generates for each patch -- with the patches
 * grouped by texture pair, one draw per group (a cell has a few dozen distinct
 * tiles). The patch blocks stay for picking and collision; with batching on
 * (setTerrainBatching) their meshes are CPU-only and the scene never draws them.
 */

#ifndef __ZZ_TERRAIN_BATCH_H__
#define __ZZ_TERRAIN_BATCH_H__

#ifndef __ZZ_VISIBLE_H__
#include "zz_visible.h"
#endif

#ifndef __ZZ_MESH_H__
#include "zz_mesh.h"
#endif

#include <vector>

//--------------------------------------------------------------------------------
class zz_mesh_terrain_batch : public zz_mesh {
public:
	/// One patch, in draw order (grouped by texture pair). Engine units.
	struct patch_desc {
		float orig_x; // west edge
		float orig_y; // north edge; rows run south from here, as in load_terrain_mesh
		int uv_type0;
		int uv_type1;
		std::vector<float> heights; // (detail+1)^2, row 0 = north
	};

	std::vector<patch_desc> patches;
	int detail_level; // faces per patch side
	float mapsize; // lightmap size
	float blocksize; // patch size

	zz_mesh_terrain_batch ();
	virtual ~zz_mesh_terrain_batch ();

	int verts_per_patch () const { return (detail_level + 1) * (detail_level + 1); }
	int faces_per_patch () const { return detail_level * detail_level * 2; }

	virtual bool load_mesh ();

	ZZ_DECLARE_DYNAMIC(zz_mesh_terrain_batch)
};

//--------------------------------------------------------------------------------
class zz_terrain_batch : public zz_visible {
	/// One draw: runits[i] carries its material, groups[i] its range in the mesh.
	struct group {
		unsigned int start_face;
		unsigned int num_faces;
		unsigned int min_vertex;
		unsigned int num_vertices;
	};
	std::vector<group> groups;
	zz_mesh_terrain_batch * batch_mesh;

public:
	zz_terrain_batch ();
	virtual ~zz_terrain_batch ();

	void set_mesh (zz_mesh_terrain_batch * mesh) { batch_mesh = mesh; }
	zz_mesh_terrain_batch * get_batch_mesh () { return batch_mesh; }

	void add_group (zz_material * material, zz_light * light,
		unsigned int start_face, unsigned int num_faces,
		unsigned int min_vertex, unsigned int num_vertices);
	int get_num_groups () const { return (int)groups.size(); }

	virtual void render (bool recursive);
	virtual bool get_transparent () { return false; }
	virtual const vec3& get_com_position_world ();
	virtual void update_bvolume (void);
	virtual void reset_bvolume (void);
	virtual void update_time (bool recursive, zz_time diff_time);
	virtual void insert_scene ();
	virtual void remove_scene ();
	virtual void before_render ();
	virtual void after_render ();

	ZZ_DECLARE_DYNAMIC(zz_terrain_batch);
};

#endif // __ZZ_TERRAIN_BATCH_H__
