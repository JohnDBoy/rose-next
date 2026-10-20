#ifndef _ROSE_RML_EASED_BAR_H_
#define _ROSE_RML_EASED_BAR_H_

/**
 * A gauge fill that eases towards its value: each frame it closes a share of the
 * remaining gap, so a jump settles in about kEaseMs (the 667 CTGuage's 400 ms) and a
 * value that moves every frame is followed smoothly. Numbers shown next to the bar
 * stay exact and immediate; only the fill eases.
 *
 * It used to restart a 400 ms linear slide whenever the value changed. A heal over
 * time raises HP a little nearly every frame (CEnduranceItem::Proc), so the slide
 * restarted every frame from where it stood and the bar froze for the whole heal --
 * the hits taken meanwhile looked ignored, then the bar jumped (2026-10-20, the food
 * ladder's 20 s foods made it obvious).
 *
 * Call Reset() when the bar starts showing something else ( another target, a
 * panel coming back into view ) so it snaps instead of sliding from stale data.
 */

#include <windows.h>
#include <math.h>

struct RoseRmlEasedBar {
    static const DWORD kEaseMs = 400;

    float fShown;
    DWORD dwLast;
    bool bPrimed;

    RoseRmlEasedBar(): fShown(0.0f), dwLast(0), bPrimed(false) {}

    void Reset() { bPrimed = false; }

    /// Advances towards fTarget ( 0..100 ). Returns true when fShown changed,
    /// i.e. when the bound width needs dirtying.
    bool Step(float fTarget, DWORD dwNow) {
        if (!bPrimed) {
            fShown = fTarget;
            dwLast = dwNow;
            bPrimed = true;
            return true;
        }

        const DWORD dwDt = dwNow - dwLast;
        dwLast = dwNow;
        if (fShown == fTarget)
            return false;

        /// time constant kEaseMs / 3: 95% of a jump is covered within kEaseMs
        const float fGap = fTarget - fShown;
        const float fShare = 1.0f - expf(-3.0f * (float)dwDt / (float)kEaseMs);
        float fNext = fShown + fGap * fShare;
        if (fabsf(fTarget - fNext) < 0.05f) /// a twentieth of a percent: done
            fNext = fTarget;
        if (fNext == fShown)
            return false;

        fShown = fNext;
        return true;
    }
};

#endif /// _ROSE_RML_EASED_BAR_H_
