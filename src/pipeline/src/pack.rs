use std::fs;
use std::io::{BufWriter, Read, Write};
use std::path::PathBuf;

use clap::ArgMatches;
use globset::GlobSetBuilder;
use roselib::files::idx::{VfsFileMetadata, VfsIndex, VfsMetadata};
use roselib::io::RoseFile;
use walkdir::WalkDir;

use crate::command::{collect_command_globs, parse_command_file};

use crate::error::PipelineError;

pub const PACK_INPUT_DIR: &str = "INPUT_DIR";
pub const PACK_OUTPUT_DIR: &str = "OUTOUT_DIR";
pub const PACK_CONFIG_NAME: &str = "config_name";

pub const DEFAULT_IDX_NAME: &str = "data.idx";
pub const DEFAULT_VFS_NAME: &str = "rose.vfs";

pub fn pack(matches: &ArgMatches) -> Result<(), PipelineError> {
    println!("Starting pack process");

    let config_name = matches.value_of(PACK_CONFIG_NAME).unwrap();

    let input_dir = PathBuf::from(matches.value_of(PACK_INPUT_DIR).unwrap());
    if !input_dir.exists() {
        return Err(PipelineError::Message(format!(
            "Invalid input dir: {}",
            input_dir.to_str().unwrap()
        )));
    }

    println!("Setting input dir to {}", input_dir.display());

    let config_path = input_dir.join(config_name);
    if !config_path.exists() {
        return Err(PipelineError::Message(format!(
            "Config file does not exists: {}",
            config_path.to_str().unwrap()
        )));
    }

    if !config_path.is_file() {
        return Err(PipelineError::Message(format!(
            "Config argument is not a file: {}",
            config_path.to_str().unwrap()
        )));
    }

    println!("Reading config file {}", config_path.display());

    let commands = match parse_command_file(&config_path) {
        Ok(c) => c,
        Err(e) => {
            return Err(PipelineError::Message(format!(
                "Failed to load config file: {}",
                e
            )));
        }
    };

    let output_dir = PathBuf::from(matches.value_of(PACK_OUTPUT_DIR).unwrap());
    if !output_dir.exists() {
        fs::create_dir_all(&output_dir)?;
    }

    println!("Setting output dir to {}", output_dir.display());

    let globs = match collect_command_globs(commands.as_slice()) {
        Ok(c) => c,
        Err(e) => {
            return Err(PipelineError::Message(format!(
                "Failed to build file globs: {}",
                e
            )));
        }
    };

    let empty_globset = GlobSetBuilder::new();

    // Compile the glob sets once. They used to be rebuilt inside the file loop,
    // twice per file -- 77,000 compilations for a 38,655-file tree -- which is
    // where most of a 7-minute bake went (2026-10-11; the I/O itself is ~30 s).
    let no_pack_globs = globs.get("nopack").unwrap_or(&empty_globset).build()?;
    let ignore_globs = globs.get("ignore").unwrap_or(&empty_globset).build()?;

    // The .vfs format stores each file's offset in a 32-BIT field
    // (triggervfs FileEntry::lFileOffset), which triggervfs reads as UNSIGNED --
    // so the ceiling is 4 GiB. It was a *signed* `long` until 2026-08-29, which
    // capped it at 2 GiB and corrupted silently past that: an offset wrapped
    // negative, the client seeked to garbage, and every affected file read as
    // binary noise. `cur_offset as i32` truncated without complaint, and the
    // failure looked nothing like its cause -- the files that landed past the
    // boundary were the tail of the archive, which included SCRIPTS\INIT.LUA, so
    // the client died at startup with a Lua "invalid control char" parse error
    // and a shader assert.
    //
    // Both the .idx format (VfsIndex::file_systems is a list) and the runtime
    // (CVFS_Manager::m_vecVFS, searched by OpenFile) already support several
    // archives, so the fix is to roll over to rose_2.vfs, rose_3.vfs, ... before
    // the limit rather than to grow one file past it.
    //
    // The cap sits below 4 GiB on purpose: the check runs *before* writing a
    // file, so the margin has to absorb the largest single asset.
    const VFS_MAX_BYTES: u64 = 4_200_000_000;

    let vfs_name_for = |index: usize| -> String {
        if index == 0 {
            DEFAULT_VFS_NAME.to_string()
        } else {
            // Keep the ".vfs" extension so existing tooling still recognises it.
            format!("rose_{}.vfs", index + 1)
        }
    };

    // Buffered: the archive is written as one stream, so the offset of each file
    // is known arithmetically (`cur_offset`) and no seek is needed per file.
    let create_vfs = |name: &str| -> Result<BufWriter<fs::File>, PipelineError> {
        let path = output_dir.join(name);
        fs::File::create(&path)
            .map(|f| BufWriter::with_capacity(8 << 20, f))
            .map_err(|e| {
                PipelineError::Message(format!(
                    "Failed to create vfs file {}: {}",
                    path.display(),
                    e
                ))
            })
    };

    let mut vfs_index = 0usize;
    let mut vfs = create_vfs(&vfs_name_for(vfs_index))?;
    let mut cur_offset: u64 = 0;
    let mut input_data: Vec<u8> = Vec::new();
    // Counted, not printed: one "Packing file" line per file was 38,655 lines, and
    // pack.ps1 collects stdout through Start-Process's redirect pipe, which
    // PowerShell reads line by line -- ~140 s of a 153 s bake for a packer that
    // runs in 14 s (2026-10-11). Ignored and copied files are rare and still named.
    let mut packed_files: u64 = 0;
    let mut packed_bytes: u64 = 0;

    // Completed archives, pushed into the index once the walk finishes.
    let mut finished_metadata: Vec<VfsMetadata> = Vec::new();

    let mut vfs_metadata = VfsMetadata::new();
    vfs_metadata.filename = PathBuf::from(vfs_name_for(vfs_index));

    let is_hidden = |entry: &walkdir::DirEntry| -> bool {
        entry
            .file_name()
            .to_str()
            .map(|s| s.starts_with('.'))
            .unwrap_or(false)
    };

    let walker = WalkDir::new(&input_dir)
        .into_iter()
        .filter_entry(|e| !is_hidden(e));

    println!(
        "Building vfs file {}",
        output_dir.join(vfs_name_for(0)).display()
    );

    for entry in walker {
        if let Ok(ent) = entry {
            if !ent.file_type().is_file() {
                continue;
            }

            let input_path = ent.into_path();
            let input_relative_path = input_path.strip_prefix(&input_dir).unwrap().to_path_buf();

            if ignore_globs.is_match(&input_relative_path) {
                println!("Ignoring file {}", input_path.display());
                continue;
            }

            if no_pack_globs.is_match(&input_relative_path) {
                let output_path = output_dir.join(input_relative_path);
                let output_path_parent = output_path.parent().unwrap();

                if let Err(e) = fs::create_dir_all(&output_path_parent) {
                    return Err(PipelineError::Message(format!(
                        "Error creating output dir {}: {}",
                        output_path_parent.display(),
                        e
                    )));
                }

                println!("Copying file {}", input_path.display());
                if let Err(e) = fs::copy(&input_path, &output_path) {
                    return Err(PipelineError::Message(format!(
                        "Error copying file {}: {}",
                        input_path.display(),
                        e
                    )));
                }
                continue;
            }

            let mut input_file = match fs::File::open(&input_path) {
                Ok(f) => f,
                Err(e) => {
                    return Err(PipelineError::Message(format!(
                        "Failed to open file {}: {}",
                        input_path.display(),
                        e
                    )));
                }
            };

            input_data.clear();
            let input_size = match input_file.read_to_end(&mut input_data) {
                Ok(s) => s,
                Err(e) => {
                    return Err(PipelineError::Message(format!(
                        "Failed to read file {}: {}",
                        input_path.display(),
                        e
                    )));
                }
            };

            // Roll over to a new archive before this file would push us past the
            // 32-bit offset limit. See VFS_MAX_BYTES above.
            if cur_offset + input_size as u64 > VFS_MAX_BYTES {
                vfs.flush()?;
                finished_metadata.push(vfs_metadata);

                vfs_index += 1;
                let next_name = vfs_name_for(vfs_index);
                println!(
                    "  vfs would exceed {} MB, rolling over to {}",
                    VFS_MAX_BYTES / 1_048_576,
                    next_name
                );

                vfs = create_vfs(&next_name)?;
                vfs_metadata = VfsMetadata::new();
                vfs_metadata.filename = PathBuf::from(next_name);
                cur_offset = 0;
            }

            if let Err(e) = vfs.write_all(&input_data) {
                return Err(PipelineError::Message(format!(
                    "Failed to write file {} to vfs: {}",
                    input_path.display(),
                    e
                )));
            };

            // Belt and braces: the rollover above should make this unreachable,
            // but a silent truncation here corrupts the archive in a way that is
            // extremely hard to trace back (see VFS_MAX_BYTES). Fail loudly.
            if cur_offset > u32::MAX as u64 || input_size > i32::MAX as usize {
                return Err(PipelineError::Message(format!(
                    "vfs offset overflow packing {} (offset {}, size {}): the .vfs \
                     format stores 32-bit unsigned offsets, 4 GB is the ceiling. A bug in the \
                     rollover logic.",
                    input_path.display(),
                    cur_offset,
                    input_size
                )));
            }

            // Client requires upper case
            let relative_path_upper = input_relative_path.to_string_lossy().to_uppercase();

            let mut vfs_file_metadata = VfsFileMetadata::new();
            vfs_file_metadata.filepath = PathBuf::from(relative_path_upper);
            // Bit-preserving on purpose: roselib's field is i32 and writes with
            // write_i32, but triggervfs reads those same 4 bytes as unsigned. An
            // offset above 2 GB is stored as a negative i32 whose bytes are the
            // correct u32. Do not turn this into a checked conversion -- it would
            // reject exactly the offsets this exists to support.
            vfs_file_metadata.offset = (cur_offset as u32) as i32;
            vfs_file_metadata.size = input_size as i32;
            vfs_file_metadata.block_size = input_size as i32;
            vfs_file_metadata.version = 1;

            vfs_metadata.files.push(vfs_file_metadata);
            cur_offset += input_size as u64;
            packed_files += 1;
            packed_bytes += input_size as u64;
        }
    }
    vfs.flush()?;
    println!(
        "Packed {} files, {} MB",
        packed_files,
        packed_bytes / 1_048_576
    );
    let output_idx_path = output_dir.join(DEFAULT_IDX_NAME);

    println!("Saving vfs index file {}", output_idx_path.display());

    let mut vfs_idx = VfsIndex::new();
    vfs_idx.base_version = 100;
    vfs_idx.current_version = 100;

    finished_metadata.push(vfs_metadata);
    if finished_metadata.len() > 1 {
        println!(
            "Packed into {} vfs archives (32-bit offset limit)",
            finished_metadata.len()
        );
    }
    for metadata in finished_metadata {
        vfs_idx.file_systems.push(metadata);
    }

    if let Err(e) = vfs_idx.write_to_path(&output_idx_path) {
        return Err(PipelineError::Message(format!(
            "Failed to save idx {}: {}",
            output_idx_path.display(),
            e
        )));
    };

    Ok(())
}
