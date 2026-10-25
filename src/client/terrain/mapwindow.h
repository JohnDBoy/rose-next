#pragma once

/// The square window of map cells (160 m each) kept loaded around the avatar.
///
/// The original client hardcoded a 3x3 window (radius 1): terrain ended 160-320 m
/// away and every object vanished with the cell holding its pivot -- a 336 m Muris
/// canyon wall popped in whole, 61 m in front of the player, on a border crossing.
/// The radius is now [VIDEO] TERRAIN_RADIUS (1 = 3x3, 2 = 5x5); every array sized
/// by the window uses the _MAX values below, and the load / unload tables are
/// generated here instead of written out by hand.
///
/// Self-contained on purpose (no client headers) so the tables can be checked
/// outside the game: at radius 1 Build() must reproduce the original hand-written
/// s_SecAdjPos / s_AddSecIdx / s_SubSecIdx exactly, entry for entry.

#define MAP_WINDOW_RADIUS_MAX 2
#define MAP_WINDOW_SPAN_MAX (2 * MAP_WINDOW_RADIUS_MAX + 1)
#define MAP_WINDOW_CELLS_MAX (MAP_WINDOW_SPAN_MAX * MAP_WINDOW_SPAN_MAX)

/// Direction of a border crossing (bit flags). Left/up = towards lower indices.
#define MOVE_UPDATE_ALL 0x00
#define MOVE_UPDATE_LEFT 0x01
#define MOVE_UPDATE_RIGHT 0x02
#define MOVE_UPDATE_UP 0x04
#define MOVE_UPDATE_DOWN 0x08
#define MOVE_UPDATE_LU (MOVE_UPDATE_LEFT | MOVE_UPDATE_UP) // 0x05
#define MOVE_UPDATE_RU (MOVE_UPDATE_RIGHT | MOVE_UPDATE_UP) // 0x06
#define MOVE_UPDATE_LD (MOVE_UPDATE_LEFT | MOVE_UPDATE_DOWN) // 0x09
#define MOVE_UPDATE_RD (MOVE_UPDATE_RIGHT | MOVE_UPDATE_DOWN) // 0x0a
#define MOVE_UPDATE_FLAG_COUNT 11

namespace MapWindow {

struct Offset {
    short m_nX;
    short m_nY;
};

struct Tables {
    short m_nRadius;
    /// Cell index -> offset from the centre cell, row-major from the top-left.
    Offset m_Adj[MAP_WINDOW_CELLS_MAX];
    /// Per move flag, the cells (relative to the NEW centre) that enter the window.
    /// -1 terminated.
    char m_Add[MOVE_UPDATE_FLAG_COUNT][MAP_WINDOW_CELLS_MAX + 1];
    /// Per move flag, the cells (relative to the OLD centre) that leave it.
    char m_Sub[MOVE_UPDATE_FLAG_COUNT][MAP_WINDOW_CELLS_MAX + 1];
};

inline char
CellIndex(short nRadius, int iDX, int iDY) {
    const int iSpan = 2 * nRadius + 1;
    return (char)((iDY + nRadius) * iSpan + (iDX + nRadius));
}

/// The edge column on side iSX (top to bottom), then the edge row on side iSY
/// (left to right) without the corner the column already holds -- the order the
/// original tables used.
inline void
FillEdge(char* pList, short nRadius, int iSX, int iSY) {
    int iN = 0;
    if (iSX) {
        for (int iDY = -nRadius; iDY <= nRadius; iDY++)
            pList[iN++] = CellIndex(nRadius, iSX * nRadius, iDY);
    }
    if (iSY) {
        for (int iDX = -nRadius; iDX <= nRadius; iDX++) {
            if (iSX && iDX == iSX * nRadius)
                continue;
            pList[iN++] = CellIndex(nRadius, iDX, iSY * nRadius);
        }
    }
    pList[iN] = -1;
}

inline void
Build(Tables& t, short nRadius) {
    if (nRadius < 1)
        nRadius = 1;
    if (nRadius > MAP_WINDOW_RADIUS_MAX)
        nRadius = MAP_WINDOW_RADIUS_MAX;

    const int iSpan = 2 * nRadius + 1;
    const int iCells = iSpan * iSpan;

    t.m_nRadius = nRadius;
    for (int iI = 0; iI < MAP_WINDOW_CELLS_MAX; iI++) {
        t.m_Adj[iI].m_nX = (short)(iI % iSpan - nRadius);
        t.m_Adj[iI].m_nY = (short)(iI / iSpan - nRadius);
    }

    for (int iF = 0; iF < MOVE_UPDATE_FLAG_COUNT; iF++) {
        t.m_Add[iF][0] = -1;
        t.m_Sub[iF][0] = -1;
    }

    for (int iI = 0; iI < iCells; iI++) {
        t.m_Add[MOVE_UPDATE_ALL][iI] = (char)iI;
        t.m_Sub[MOVE_UPDATE_ALL][iI] = (char)iI;
    }
    t.m_Add[MOVE_UPDATE_ALL][iCells] = -1;
    t.m_Sub[MOVE_UPDATE_ALL][iCells] = -1;

    for (int iF = 1; iF < MOVE_UPDATE_FLAG_COUNT; iF++) {
        /// Left and right together (0x03, 0x07) cannot happen; they stay empty.
        if ((iF & MOVE_UPDATE_LEFT) && (iF & MOVE_UPDATE_RIGHT))
            continue;

        const int iSX = (iF & MOVE_UPDATE_LEFT) ? -1 : (iF & MOVE_UPDATE_RIGHT) ? 1 : 0;
        const int iSY = (iF & MOVE_UPDATE_UP) ? -1 : (iF & MOVE_UPDATE_DOWN) ? 1 : 0;

        FillEdge(t.m_Add[iF], nRadius, iSX, iSY);
        FillEdge(t.m_Sub[iF], nRadius, -iSX, -iSY);
    }
}

} // namespace MapWindow
