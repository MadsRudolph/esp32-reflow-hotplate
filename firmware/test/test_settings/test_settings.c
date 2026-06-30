/*
 * test_settings.c — Unity tests for core/settings using an in-memory fake
 * storage backend.
 *
 * Fake state: a struct holding profile_t arr[8] and int n.
 * Passed as ctx through storage_if.  load copies arr→out; save copies arr←in.
 * This lets settings_begin's "empty?" check work: first run n==0 triggers
 * seeding; after save n==2; a fresh settings_begin with same ctx reloads 2.
 */

#include <unity.h>
#include <string.h>
#include "settings.h"
#include "profile.h"

/* -----------------------------------------------------------------------
 * In-memory fake storage backend
 * ----------------------------------------------------------------------- */

typedef struct {
    profile_t arr[SETTINGS_MAX_PROFILES];
    int       n;
    int       save_call_count;
} fake_store_t;

static int fake_load(void *ctx, profile_t *out, int *n_out, int max)
{
    fake_store_t *fs = (fake_store_t *)ctx;
    int count = fs->n < max ? fs->n : max;
    memcpy(out, fs->arr, count * sizeof(profile_t));
    *n_out = count;
    return 0;
}

static int fake_save(void *ctx, const profile_t *arr, int n)
{
    fake_store_t *fs = (fake_store_t *)ctx;
    if (n > SETTINGS_MAX_PROFILES) n = SETTINGS_MAX_PROFILES;
    memcpy(fs->arr, arr, n * sizeof(profile_t));
    fs->n = n;
    fs->save_call_count++;
    return 0;
}

static storage_if make_storage_if(fake_store_t *fs)
{
    storage_if io;
    io.load = fake_load;
    io.save = fake_save;
    io.ctx  = fs;
    return io;
}

/* -----------------------------------------------------------------------
 * Unity setUp / tearDown
 * ----------------------------------------------------------------------- */

void setUp(void) {}
void tearDown(void) {}

/* -----------------------------------------------------------------------
 * Test 1: begin on empty storage seeds exactly 2 valid defaults + persists
 * ----------------------------------------------------------------------- */
static void test_begin_on_empty_seeds_two_defaults(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));   /* n == 0 → empty */

    settings_t s;
    int rc = settings_begin(&s, make_storage_if(&fs));

    TEST_ASSERT_EQUAL_INT(0, rc);

    /* 2 profiles in memory */
    TEST_ASSERT_EQUAL_INT(2, settings_count(&s));

    /* Both are valid */
    const profile_t *p0 = settings_get(&s, 0);
    const profile_t *p1 = settings_get(&s, 1);
    TEST_ASSERT_NOT_NULL(p0);
    TEST_ASSERT_NOT_NULL(p1);
    TEST_ASSERT_TRUE(profile_validate(p0));
    TEST_ASSERT_TRUE(profile_validate(p1));

    /* Persisted to fake store (save was called) */
    TEST_ASSERT_EQUAL_INT(2, fs.n);
    TEST_ASSERT_EQUAL_INT(1, fs.save_call_count);
}

/* -----------------------------------------------------------------------
 * Test 2: begin on non-empty storage does NOT re-seed (loads what's there)
 * ----------------------------------------------------------------------- */
static void test_begin_on_nonempty_does_not_reseed(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    /* Pre-populate fake store with 1 custom profile */
    profile_t custom;
    memset(&custom, 0, sizeof(custom));
    strncpy(custom.name, "Custom", PROFILE_NAME_LEN - 1);
    custom.n_stages = 1;
    strncpy(custom.stages[0].name, "Stage", PROFILE_NAME_LEN - 1);
    custom.stages[0].target_c   = 200.0f;
    custom.stages[0].duration_s = 60;
    fs.arr[0] = custom;
    fs.n = 1;

    settings_t s;
    int rc = settings_begin(&s, make_storage_if(&fs));

    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_INT(1, settings_count(&s));

    const profile_t *p = settings_get(&s, 0);
    TEST_ASSERT_NOT_NULL(p);
    TEST_ASSERT_EQUAL_STRING("Custom", p->name);

    /* No save should have been called (we loaded existing data) */
    TEST_ASSERT_EQUAL_INT(0, fs.save_call_count);
}

/* -----------------------------------------------------------------------
 * Test 3: upsert(-1, valid) appends + persists; count grows
 * ----------------------------------------------------------------------- */
static void test_upsert_append_valid_increases_count(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));
    /* After begin: count == 2, save_call_count == 1 */

    profile_t p;
    profile_default_leaded(&p);
    strncpy(p.name, "Extra", PROFILE_NAME_LEN - 1);

    int prev_count = settings_count(&s);
    int rc = settings_upsert(&s, -1, &p);

    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_INT(prev_count + 1, settings_count(&s));

    /* Fake store updated */
    TEST_ASSERT_EQUAL_INT(prev_count + 1, fs.n);
    TEST_ASSERT_EQUAL_INT(2, fs.save_call_count); /* begin + upsert */
}

/* -----------------------------------------------------------------------
 * Test 4: upsert with INVALID profile returns nonzero, count unchanged
 * ----------------------------------------------------------------------- */
static void test_upsert_invalid_profile_rejected(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));

    int count_before = settings_count(&s);
    int saves_before = fs.save_call_count;

    /* Build a clearly invalid profile: empty name, 0 stages */
    profile_t bad;
    memset(&bad, 0, sizeof(bad));
    /* name[0] == '\0' and n_stages == 0 → invalid per profile_validate */

    int rc = settings_upsert(&s, -1, &bad);

    TEST_ASSERT_NOT_EQUAL(0, rc);                     /* must reject */
    TEST_ASSERT_EQUAL_INT(count_before, settings_count(&s)); /* count unchanged */
    TEST_ASSERT_EQUAL_INT(saves_before, fs.save_call_count); /* no save */
}

/* -----------------------------------------------------------------------
 * Test 5: upsert with idx>=0 replaces in place
 * ----------------------------------------------------------------------- */
static void test_upsert_replace_in_place(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));

    /* Replace slot 0 */
    profile_t repl;
    profile_default_lead_free(&repl);
    strncpy(repl.name, "Replaced", PROFILE_NAME_LEN - 1);

    int count_before = settings_count(&s);
    int rc = settings_upsert(&s, 0, &repl);

    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_INT(count_before, settings_count(&s)); /* count unchanged */

    const profile_t *p = settings_get(&s, 0);
    TEST_ASSERT_NOT_NULL(p);
    TEST_ASSERT_EQUAL_STRING("Replaced", p->name);
}

/* -----------------------------------------------------------------------
 * Test 6: delete removes + persists; count decreases
 * ----------------------------------------------------------------------- */
static void test_delete_removes_and_persists(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));

    /* Add a 3rd profile so we can safely delete */
    profile_t extra;
    profile_default_leaded(&extra);
    strncpy(extra.name, "Extra", PROFILE_NAME_LEN - 1);
    settings_upsert(&s, -1, &extra);

    int count_before = settings_count(&s);  /* == 3 */
    int saves_before = fs.save_call_count;

    int rc = settings_delete(&s, 2); /* delete last */

    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_INT(count_before - 1, settings_count(&s));
    TEST_ASSERT_EQUAL_INT(saves_before + 1, fs.save_call_count);
    TEST_ASSERT_EQUAL_INT(count_before - 1, fs.n);
}

/* -----------------------------------------------------------------------
 * Test 7: delete refuses to drop below 1 profile
 * ----------------------------------------------------------------------- */
static void test_delete_refuses_below_one(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));

    /* Delete down to 1 */
    int rc1 = settings_delete(&s, 0);
    TEST_ASSERT_EQUAL_INT(0, rc1);
    TEST_ASSERT_EQUAL_INT(1, settings_count(&s));

    /* Now at exactly 1 — next delete must refuse */
    int saves_before = fs.save_call_count;
    int rc2 = settings_delete(&s, 0);

    TEST_ASSERT_NOT_EQUAL(0, rc2);              /* must refuse */
    TEST_ASSERT_EQUAL_INT(1, settings_count(&s)); /* still 1 */
    TEST_ASSERT_EQUAL_INT(saves_before, fs.save_call_count); /* no save */
}

/* -----------------------------------------------------------------------
 * Test 8: round-trip — second settings_begin reloads what was saved
 * ----------------------------------------------------------------------- */
static void test_round_trip_reloads_saved_state(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    /* First session: begin (seeds 2), add 1 more */
    {
        settings_t s;
        settings_begin(&s, make_storage_if(&fs));

        profile_t extra;
        profile_default_lead_free(&extra);
        strncpy(extra.name, "RoundTrip", PROFILE_NAME_LEN - 1);
        settings_upsert(&s, -1, &extra);
        /* fake store now has 3 entries */
    }

    TEST_ASSERT_EQUAL_INT(3, fs.n);

    /* Second session: fresh settings_t, same fake store */
    {
        settings_t s2;
        int rc = settings_begin(&s2, make_storage_if(&fs));

        TEST_ASSERT_EQUAL_INT(0, rc);
        TEST_ASSERT_EQUAL_INT(3, settings_count(&s2));

        const profile_t *p = settings_get(&s2, 2);
        TEST_ASSERT_NOT_NULL(p);
        TEST_ASSERT_EQUAL_STRING("RoundTrip", p->name);
    }
}

/* -----------------------------------------------------------------------
 * Test 9: settings_get returns NULL for out-of-range index
 * ----------------------------------------------------------------------- */
static void test_get_out_of_range_returns_null(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));

    TEST_ASSERT_NULL(settings_get(&s, -1));
    TEST_ASSERT_NULL(settings_get(&s, settings_count(&s)));
    TEST_ASSERT_NULL(settings_get(&s, 100));
}

/* -----------------------------------------------------------------------
 * Test 10: delete compacts array (no holes)
 * ----------------------------------------------------------------------- */
static void test_delete_compacts_array(void)
{
    fake_store_t fs;
    memset(&fs, 0, sizeof(fs));

    settings_t s;
    settings_begin(&s, make_storage_if(&fs));

    /* Rename slot 1 so we can identify it after deletion */
    profile_t p1;
    profile_default_lead_free(&p1);
    strncpy(p1.name, "SlotOne", PROFILE_NAME_LEN - 1);
    settings_upsert(&s, 1, &p1);

    /* Delete slot 0; slot 1 ("SlotOne") should shift to slot 0 */
    int rc = settings_delete(&s, 0);
    TEST_ASSERT_EQUAL_INT(0, rc);
    TEST_ASSERT_EQUAL_INT(1, settings_count(&s));

    const profile_t *p = settings_get(&s, 0);
    TEST_ASSERT_NOT_NULL(p);
    TEST_ASSERT_EQUAL_STRING("SlotOne", p->name);
}

/* -----------------------------------------------------------------------
 * Main
 * ----------------------------------------------------------------------- */
int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_begin_on_empty_seeds_two_defaults);
    RUN_TEST(test_begin_on_nonempty_does_not_reseed);
    RUN_TEST(test_upsert_append_valid_increases_count);
    RUN_TEST(test_upsert_invalid_profile_rejected);
    RUN_TEST(test_upsert_replace_in_place);
    RUN_TEST(test_delete_removes_and_persists);
    RUN_TEST(test_delete_refuses_below_one);
    RUN_TEST(test_round_trip_reloads_saved_state);
    RUN_TEST(test_get_out_of_range_returns_null);
    RUN_TEST(test_delete_compacts_array);
    return UNITY_END();
}
