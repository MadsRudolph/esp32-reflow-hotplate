#ifndef SETTINGS_H
#define SETTINGS_H

#ifdef __cplusplus
extern "C" {
#endif

#include "profile.h"

/* Maximum number of profiles the settings store can hold. */
#define SETTINGS_MAX_PROFILES 8

/*
 * Injected storage backend interface.
 *
 * load: Read up to `max` profiles into `out[]`; write actual count to *n_out.
 *       Return 0 on success, nonzero on error.
 * save: Write `n` profiles from `arr[]` to persistent storage.
 *       Return 0 on success, nonzero on error.
 * ctx:  Opaque pointer passed to both functions (e.g. NVS handle or fake state).
 */
typedef struct {
    int (*load)(void *ctx, profile_t *out, int *n_out, int max);
    int (*save)(void *ctx, const profile_t *arr, int n);
    void *ctx;
} storage_if;

/*
 * Settings store state.  Callers must not access fields directly; use the
 * API functions below.
 */
typedef struct {
    storage_if io;
    profile_t  items[SETTINGS_MAX_PROFILES];
    int        n;
} settings_t;

/*
 * Initialise the settings store with the given storage backend.
 *
 * Calls io.load.  If the backend reports 0 profiles (first run / blank NVS),
 * seeds items[0] = leaded default, items[1] = lead-free default, n = 2,
 * and calls io.save to persist the seeds.
 *
 * Returns 0 on success, nonzero if load or save returns an error.
 */
int settings_begin(settings_t *s, storage_if io);

/*
 * Return the number of profiles currently in the store.
 */
int settings_count(const settings_t *s);

/*
 * Return a const pointer to the profile at index `idx`, or NULL if idx is
 * out of range (idx < 0 or idx >= count).
 */
const profile_t *settings_get(const settings_t *s, int idx);

/*
 * Insert or replace a profile.
 *
 * Validates `p` via profile_validate first — if invalid, returns nonzero
 * immediately without mutating the store or calling io.save.
 *
 * idx < 0  : append (requires n < SETTINGS_MAX_PROFILES; returns nonzero if full).
 * idx >= 0 : replace items[idx] (returns nonzero if idx >= n).
 *
 * On success, calls io.save and returns 0.
 */
int settings_upsert(settings_t *s, int idx, const profile_t *p);

/*
 * Delete the profile at index `idx` and compact the array.
 *
 * Refuses (returns nonzero, no mutation, no save) if:
 *   - idx is out of range, or
 *   - the store currently holds only 1 profile (must keep >= 1).
 *
 * On success, calls io.save and returns 0.
 */
int settings_delete(settings_t *s, int idx);

#ifdef __cplusplus
}
#endif

#endif /* SETTINGS_H */
