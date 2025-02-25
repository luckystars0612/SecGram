#include <archive.h>
#include <archive_entry.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdarg.h>
#include <pthread.h>
#include <rabbitmq-c/amqp.h>
#include <rabbitmq-c/framing.h>

#define BUFFER_SIZE 4096
#define MAX_FILES 10  // Maximum concurrent files (adjust based on system)

typedef struct {
    char *file_path;
} FileTask;

pthread_mutex_t queue_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t queue_not_empty = PTHREAD_COND_INITIALIZER;
FileTask *file_queue[MAX_FILES];
int queue_front = 0, queue_rear = 0, queue_size = 0;

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
        log_error("Failed to open archive %s: %s", filename, archive_error_string(a));
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
        
        log_info("Extracting %s from %s", pathname, filename);

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
        log_error("Archive read error for %s: %s", filename, archive_error_string(a));
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
        log_error("Failed to open files for copying %s to %s: %s", src, dest, strerror(errno));
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

// Thread function to process a file
void *process_file(void *arg) {
    FileTask *task = (FileTask *)arg;
    const char *file_path = task->file_path;
    const char *output_dir = "extracted";

    log_info("Processing file: %s", file_path);

    if (access(file_path, F_OK) == -1) {
        log_error("File does not exist: %s", file_path);
        free(task->file_path);
        free(task);
        return NULL;
    }

    if (is_archive(file_path)) {
        log_info("File %s is an archive. Starting extraction...", file_path);
        if (extract_archive(file_path, output_dir) == 0) {
            log_info("Extraction completed successfully for %s to %s", file_path, output_dir);
        } else {
            log_error("Extraction failed for %s", file_path);
        }
    } else {
        log_warning("File %s is not an archive", file_path);
        char dest_path[1024];
        const char *base_name = strrchr(file_path, '/') ? strrchr(file_path, '/') + 1 : file_path;
        snprintf(dest_path, sizeof(dest_path), "%s/%s", output_dir, base_name);
        if (mkdir_p(output_dir, 0777) == -1) {
            log_error("Failed to create output directory for %s: %s", file_path, strerror(errno));
            free(task->file_path);
            free(task);
            return NULL;
        }
        if (copy_file(file_path, dest_path) != 0) {
            log_error("Failed to copy non-archive file %s", file_path);
        } else {
            log_info("Copied non-archive file %s to %s", file_path, dest_path);
        }
    }

    free(task->file_path);
    free(task);
    return NULL;
}

// Add a file task to the queue
int enqueue_file(const char *file_path) {
    pthread_mutex_lock(&queue_mutex);
    if (queue_size >= MAX_FILES) {
        pthread_mutex_unlock(&queue_mutex);
        log_error("Queue full, cannot enqueue %s", file_path);
        return -1;
    }

    FileTask *task = malloc(sizeof(FileTask));
    if (!task) {
        pthread_mutex_unlock(&queue_mutex);
        log_error("Failed to allocate memory for task %s", file_path);
        return -1;
    }

    task->file_path = strdup(file_path);
    if (!task->file_path) {
        free(task);
        pthread_mutex_unlock(&queue_mutex);
        log_error("Failed to duplicate path for %s", file_path);
        return -1;
    }

    file_queue[queue_rear] = task;
    queue_rear = (queue_rear + 1) % MAX_FILES;
    queue_size++;
    pthread_cond_signal(&queue_not_empty);
    pthread_mutex_unlock(&queue_mutex);
    return 0;
}

// Dequeue a file task from the queue
FileTask *dequeue_file() {
    pthread_mutex_lock(&queue_mutex);
    while (queue_size == 0) {
        pthread_cond_wait(&queue_not_empty, &queue_mutex);
    }

    FileTask *task = file_queue[queue_front];
    queue_front = (queue_front + 1) % MAX_FILES;
    queue_size--;
    pthread_mutex_unlock(&queue_mutex);
    return task;
}

// RabbitMQ connection and callback (updated for rabbitmq-c)
void consume_messages() {
    amqp_connection_state_t conn;
    amqp_socket_t *socket = NULL;
    amqp_channel_t channel = 1;
    amqp_frame_t frame;  // Declare frame here

    conn = amqp_new_connection();
    socket = amqp_tcp_socket_new(conn);  // Correct API for rabbitmq-c
    if (!socket) {
        log_error("Failed to create socket");
        return;
    }

    int status = amqp_socket_open(socket, "rabbitmq", 5672);
    if (status != AMQP_STATUS_OK) {
        log_error("Failed to open socket to rabbitmq: %s", amqp_error_string2(status));
        amqp_destroy_connection(conn);
        return;
    }

    amqp_rpc_reply_t reply = amqp_login(conn, "/", 0, 131072, 0, AMQP_SASL_METHOD_PLAIN, "guest", "guest");
    if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
        log_error("Failed to login to RabbitMQ: %s", amqp_error_string2(reply.library_error));
        amqp_destroy_connection(conn);
        return;
    }

    amqp_channel_open(conn, channel);
    reply = amqp_get_rpc_reply(conn);
    if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
        log_error("Failed to open channel: %s", amqp_error_string2(reply.library_error));
        amqp_channel_close(conn, channel, AMQP_REPLY_SUCCESS);
        amqp_connection_close(conn, AMQP_REPLY_SUCCESS);
        amqp_destroy_connection(conn);
        return;
    }

    amqp_queue_declare(conn, channel, amqp_cstring_bytes("file_queue"), 0, 0, 0, 1, amqp_empty_table);
    reply = amqp_get_rpc_reply(conn);
    if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
        log_error("Failed to declare queue: %s", amqp_error_string2(reply.library_error));
        goto cleanup;
    }

    amqp_basic_consume(conn, channel, amqp_cstring_bytes("file_queue"), amqp_empty_bytes, 0, 1, 0, amqp_empty_table);
    reply = amqp_get_rpc_reply(conn);
    if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
        log_error("Failed to consume from queue: %s", amqp_error_string2(reply.library_error));
        goto cleanup;
    }

    while (1) {
        amqp_maybe_release_buffers(conn);
        int frame_status = amqp_simple_wait_frame(conn, &frame);  // Returns int, not amqp_rpc_reply_t
        if (frame_status != AMQP_STATUS_OK) {
            log_error("RabbitMQ error: %s", amqp_error_string2(frame_status));
            break;
        }

        if (frame.frame_type == AMQP_FRAME_METHOD && frame.payload.method.id == AMQP_BASIC_DELIVER_METHOD) {
            amqp_message_t message;
            reply = amqp_read_message(conn, channel, &message, 0);
            if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
                log_error("Failed to read message: %s", amqp_error_string2(reply.library_error));
                continue;
            }

            char *file_path = strndup((char *)message.body.bytes, message.body.len);
            if (file_path) {
                enqueue_file(file_path);
                free(file_path);
            }

            amqp_destroy_message(&message);
            amqp_basic_ack(conn, channel, frame.payload.method.id, 0);
        }
    }

cleanup:
    amqp_channel_close(conn, channel, AMQP_REPLY_SUCCESS);
    amqp_connection_close(conn, AMQP_REPLY_SUCCESS);
    amqp_destroy_connection(conn);
}

int main() {
    pthread_t threads[MAX_FILES];
    for (int i = 0; i < MAX_FILES; i++) {
        if (pthread_create(&threads[i], NULL, process_file, NULL) != 0) {
            log_error("Failed to create thread %d", i);
            return 1;
        }
    }

    // Start RabbitMQ consumer in a separate thread
    pthread_t consumer_thread;
    if (pthread_create(&consumer_thread, NULL, (void *(*)(void *))consume_messages, NULL) != 0) {
        log_error("Failed to create consumer thread");
        return 1;
    }

    // Wait for threads to finish (simplified; in practice, use signals or a shutdown mechanism)
    for (int i = 0; i < MAX_FILES; i++) {
        pthread_join(threads[i], NULL);
    }
    pthread_join(consumer_thread, NULL);

    return 0;
}