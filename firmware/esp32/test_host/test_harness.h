/* test_harness.h - tiny self-contained assert harness (no external dependency). */
#pragma once
#include <math.h>
#include <stdio.h>
#include <string.h>

typedef void (*th_fn)(void);
typedef struct { const char *tname; th_fn fn; } th_case_t;
#define TH_MAX_CASES 128
extern th_case_t th_cases[TH_MAX_CASES];
extern int th_ncases, th_fail_in_case, th_asserts;

#define TEST(name)                                                         \
    static void name(void);                                                \
    __attribute__((constructor)) static void reg_##name(void)              \
    { th_cases[th_ncases].tname = #name; th_cases[th_ncases++].fn = name; } \
    static void name(void)

#define ASSERT_TRUE(c)                                                     \
    do { th_asserts++; if (!(c)) { th_fail_in_case++;                      \
        printf("    FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)
#define ASSERT_EQ(a, b)                                                    \
    do { long long _a = (long long)(a), _b = (long long)(b); th_asserts++; \
        if (_a != _b) { th_fail_in_case++;                                 \
        printf("    FAIL %s:%d: %s == %s (%lld vs %lld)\n", __FILE__, __LINE__, #a, #b, _a, _b); } } while (0)
#define ASSERT_NEAR(a, b, tol)                                             \
    do { double _a = (double)(a), _b = (double)(b); th_asserts++;          \
        if (fabs(_a - _b) > (double)(tol)) { th_fail_in_case++;            \
        printf("    FAIL %s:%d: %s ~ %s (%g vs %g, tol %g)\n", __FILE__, __LINE__, #a, #b, _a, _b, (double)(tol)); } } while (0)

/* Define once, in the main file: TH_MAIN */
#define TH_MAIN                                                            \
    th_case_t th_cases[TH_MAX_CASES]; int th_ncases, th_fail_in_case, th_asserts; \
    int main(void) {                                                       \
        int failed = 0;                                                    \
        for (int i = 0; i < th_ncases; i++) {                              \
            th_fail_in_case = 0; th_cases[i].fn();                         \
            printf("[%s] %s\n", th_fail_in_case ? "FAIL" : "PASS", th_cases[i].tname); \
            if (th_fail_in_case) failed++;                                 \
        }                                                                  \
        printf("%d tests, %d passed, %d failed, %d assertions\n", th_ncases, th_ncases - failed, failed, th_asserts); \
        return failed ? 1 : 0;                                             \
    }
