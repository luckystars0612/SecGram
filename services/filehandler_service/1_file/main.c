#include <archive.h>
#include <archive_entry.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdarg.h>

#define BUFFER_SIZE 4096

// Logging functions with variable arguments
void log_info(const char *format, ...) {
    va_list args;
    va_start(args, format);
    printf("INFO: ");
    vprintf(format, args);
    printf("\n");
    va_end(args);
}

void log_error(const char *format, ...) {
    va_list args;
    va_start(args, format);
    fprintf(stderr, "ERROR: ");
    vfprintf(stderr, format, args);
    fprintf(stderr, "\n");
    va_end(args);
}

void log_warning(const char *format, ...) {
    va_list args;
    va_start(args, format);
    printf("WARNING: ");
    vprintf(format, args);
    printf("\n");
    va_end(args);
}

// Recursive mkdir function to create directories and their parents
int mkdir_p(const char *path, mode_t mode) {
    char *dir = strdup(path);
    if (!dir) return -1;

    char *p = dir;
    while (*p) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(dir, mode) == -1 && errno != EEXIST) {
                free(dir);
                return -1;
            }
            *p = '/';
        }
        p++;
    }
    int result = mkdir(dir, mode);
    free(dir);
    return result == -1 && errno != EEXIST ? -1 : 0;
}

// Check if a file is an archive (extension + magic bytes)
int is_archive(const char *filename) {
    const char *ext = strrchr(filename, '.');
    if (ext) {
        if (strcmp(ext, ".zip") == 0 || strcmp(ext, ".rar") == 0 ||
            strcmp(ext, ".tar") == 0 || strcmp(ext, ".gz") == 0 ||
            strcmp(ext, ".bz2") == 0 || strcmp(ext, ".7z") == 0) {
            return 1;
        }
    }

    FILE *f = fopen(filename, "rb");
    if (!f) return 0;
    unsigned char buffer[4];
    size_t read = fread(buffer, 1, 4, f);
    fclose(f);
    if (read == 4) {
        if (buffer[0] == 'P' && buffer[1] == 'K' && buffer[2] == '\003' && buffer[3] == '\004') return 1; // ZIP
        if (buffer[0] == 'R' && buffer[1] == 'a' && buffer[2] == 'r' && buffer[3] == '!') return 1; // RAR
    }
    return 0;
}

// Extract an archive to a directory, using buffered I/O for large files
int extract_archive(const char *filename, const char *output_dir) {
    struct archive *a;
    struct archive_entry *entry;
    int r;

    a = archive_read_new();
    archive_read_support_format_all(a);
    archive_read_support_filter_all(a);

    r = archive_read_open_filename(a, filename, 10240);
    if (r != ARCHIVE_OK) {
        log_error("Failed to open archive: %s", archive_error_string(a));
        archive_read_free(a);
        return -1;
    }

    // Create output directory if it doesn’t exist (recursively)
    if (mkdir_p(output_dir, 0777) == -1) {
        log_error("Failed to create output directory %s: %s", output_dir, strerror(errno));
        archive_read_free(a);
        return -1;
    }

    while ((r = archive_read_next_header(a, &entry)) == ARCHIVE_OK) {
        const char *pathname = archive_entry_pathname(entry);
        char full_path[1024];
        snprintf(full_path, sizeof(full_path), "%s/%s", output_dir, pathname);
        
        log_info("Extracting: %s", pathname);

        // Create directories recursively for the entry path
        char *dir_path = strdup(full_path);
        if (dir_path) {
            char *last_slash = strrchr(dir_path, '/');
            if (last_slash) {
                *last_slash = '\0';
                if (mkdir_p(dir_path, 0777) == -1) {
                    log_error("Failed to create directory for %s: %s", dir_path, strerror(errno));
                    free(dir_path);
                    archive_read_free(a);
                    return -1;
                }
            }
            free(dir_path);
        }

        // Handle directories or files
        if (archive_entry_filetype(entry) == AE_IFDIR) {
            if (mkdir_p(full_path, 0777) == -1) {
                log_error("Failed to create directory %s: %s", full_path, strerror(errno));
                archive_read_free(a);
                return -1;
            }
        } else {
            FILE *out = fopen(full_path, "wb");
            if (!out) {
                log_error("Failed to create output file %s: %s", full_path, strerror(errno));
                archive_read_free(a);
                return -1;
            }

            // Use buffered I/O for large files
            const void *buff;
            size_t size;
            int64_t offset;
            while ((r = archive_read_data_block(a, &buff, &size, &offset)) == ARCHIVE_OK) {
                if (size > 0) {
                    size_t written = 0;
                    while (written < size) {
                        size_t to_write = size - written < BUFFER_SIZE ? size - written : BUFFER_SIZE;
                        if (fwrite((char*)buff + written, 1, to_write, out) != to_write) {
                            log_error("Failed to write data to %s: %s", full_path, strerror(errno));
                            fclose(out);
                            archive_read_free(a);
                            return -1;
                        }
                        written += to_write;
                    }
                }
            }
            fclose(out);
        }
    }

    if (r != ARCHIVE_EOF) {
        log_error("Archive read error: %s", archive_error_string(a));
        archive_read_free(a);
        return -1;
    }

    archive_read_free(a);
    return 0;
}

// Copy non-archive files (e.g., .txt) to output directory
int copy_file(const char *src, const char *dest) {
    FILE *in = fopen(src, "rb");
    FILE *out = fopen(dest, "wb");
    if (!in || !out) {
        log_error("Failed to open files for copying: %s", strerror(errno));
        if (in) fclose(in);
        if (out) fclose(out);
        return -1;
    }

    char buffer[BUFFER_SIZE];
    size_t bytes;
    while ((bytes = fread(buffer, 1, sizeof(buffer), in)) > 0) {
        if (fwrite(buffer, 1, bytes, out) != bytes) {
            log_error("Failed to write during copy to %s: %s", dest, strerror(errno));
            fclose(in);
            fclose(out);
            return -1;
        }
    }

    fclose(in);
    fclose(out);
    return 0;
}

int main() {
    const char *input_file = "test.zip"; // Example test file
    const char *output_dir = "extracted";

    log_info("Checking file: %s", input_file);

    if (access(input_file, F_OK) == -1) {
        log_error("File does not exist: %s", input_file);
        return 1;
    }

    if (is_archive(input_file)) {
        log_info("File is an archive. Starting extraction...");
        if (extract_archive(input_file, output_dir) == 0) {
            log_info("Extraction completed successfully to %s", output_dir);
        } else {
            log_error("Extraction failed");
            return 1;
        }
    } else {
        log_warning("File is not an archive: %s", input_file);
        char dest_path[1024];
        const char *base_name = strrchr(input_file, '/') ? strrchr(input_file, '/') + 1 : input_file;
        snprintf(dest_path, sizeof(dest_path), "%s/%s", output_dir, base_name);
        if (mkdir_p(output_dir, 0777) == -1) {
            log_error("Failed to create output directory: %s", strerror(errno));
            return 1;
        }
        if (copy_file(input_file, dest_path) != 0) {
            log_error("Failed to copy non-archive file");
            return 1;
        }
        log_info("Copied non-archive file to %s", dest_path);
    }

    return 0;
}