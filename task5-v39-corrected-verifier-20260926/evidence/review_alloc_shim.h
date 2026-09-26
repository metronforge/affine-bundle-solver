#include <stddef.h>

void *review_malloc(size_t size);
void *review_calloc(size_t count, size_t size);
void review_free(void *pointer);

#define malloc review_malloc
#define calloc review_calloc
#define free review_free
