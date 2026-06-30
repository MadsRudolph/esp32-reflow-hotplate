#include "settings.h"
#include "profile.h"
#include <string.h>

/* --------------------------------------------------------------------------
 * settings_begin
 * -------------------------------------------------------------------------- */
int settings_begin(settings_t *s, storage_if io)
{
    s->io = io;
    s->n  = 0;

    int n_loaded = 0;
    int rc = io.load(io.ctx, s->items, &n_loaded, SETTINGS_MAX_PROFILES);
    if (rc != 0)
        return rc;

    if (n_loaded > 0) {
        /* Existing profiles: use them as-is. */
        s->n = n_loaded;
        return 0;
    }

    /* Empty storage: seed the two factory defaults and persist. */
    profile_default_leaded(&s->items[0]);
    profile_default_lead_free(&s->items[1]);
    s->n = 2;

    return io.save(io.ctx, s->items, s->n);
}

/* --------------------------------------------------------------------------
 * settings_count
 * -------------------------------------------------------------------------- */
int settings_count(const settings_t *s)
{
    return s->n;
}

/* --------------------------------------------------------------------------
 * settings_get
 * -------------------------------------------------------------------------- */
const profile_t *settings_get(const settings_t *s, int idx)
{
    if (idx < 0 || idx >= s->n)
        return NULL;
    return &s->items[idx];
}

/* --------------------------------------------------------------------------
 * settings_upsert
 * -------------------------------------------------------------------------- */
int settings_upsert(settings_t *s, int idx, const profile_t *p)
{
    /* Validate before any mutation. */
    if (!profile_validate(p))
        return -1;

    if (idx < 0) {
        /* Append mode — reject if the store is already full. */
        if (s->n >= SETTINGS_MAX_PROFILES)
            return -1;
        s->items[s->n] = *p;
        s->n++;
    } else {
        /* Replace mode — reject if idx is out of range. */
        if (idx >= s->n)
            return -1;
        s->items[idx] = *p;
    }

    return s->io.save(s->io.ctx, s->items, s->n);
}

/* --------------------------------------------------------------------------
 * settings_delete
 * -------------------------------------------------------------------------- */
int settings_delete(settings_t *s, int idx)
{
    /* Refuse to go below 1 profile. */
    if (s->n <= 1)
        return -1;

    /* Validate index. */
    if (idx < 0 || idx >= s->n)
        return -1;

    /* Compact: shift elements left to fill the gap. */
    for (int i = idx; i < s->n - 1; i++)
        s->items[i] = s->items[i + 1];

    s->n--;

    return s->io.save(s->io.ctx, s->items, s->n);
}
