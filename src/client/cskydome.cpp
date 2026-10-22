/*
    $Header: /Client/CSkyDOME.cpp 23    04-10-11 6:15p Jeddli $
*/
#include "stdAFX.h"

#include "rose/io/stb.h"
#include "CSkyDOME.h"

#include <set>

CSkyDOME* CSkyDOME::m_pInstance = NULL;

//-------------------------------------------------------------------------------------------------
/// Keeps a sky's textures for the whole session. Every sky shares the material "__XXX_sky_ma",
/// so switching skies dropped the old textures' last reference and the next visit rebuilt them
/// from the file -- Junon's day01 eleven times in one short session, 2-11 ms each, some with no
/// loading screen to hide behind (character select, the Luna warp cutscene). A second material
/// per sky holds a reference (the engine shares textures by file name) and locks them, so the
/// texture manager never unbinds them either. A few MB of video memory per sky visited.
static void
PinSkyTextures(HNODE hShader, short nSkyIDX, ZSTRING pTex1, ZSTRING pTex2) {
    static std::set<short> s_pinned;
    if (!s_pinned.insert(nSkyIDX).second)
        return;

    HNODE hPin = ::loadSkyMaterial(CStr::Printf("__sky_pin_%d", nSkyIDX), hShader, pTex1, pTex2);
    if (hPin)
        ::lockMaterialTextures(hPin);
}

//-------------------------------------------------------------------------------------------------
/// Builds and pins every sky in LIST_SKY once, behind the login screen, so no sky texture is
/// built during play whatever loads it: a zone entry, a warp gate (CGameStateWarp), planet travel
/// (GameStateMovePlanet). Pinning only on first use left the warp paths building in the world
/// (Lunar night01/night02, 2-7 ms each). About a dozen textures, ~70 MB of video memory.
void
CSkyDOME::WarmAll(HNODE hShader) {
    static bool s_done = false;
    if (s_done)
        return;
    s_done = true;

    const DWORD start = timeGetTime();
    int warmed = 0;
    for (size_t row = 0; row < g_TblSKY.row_count; ++row) {
        const char* pTex1 = SKY_TEXTURE(row, 0);
        if (!pTex1 || !*pTex1 || !(CVFSManager::GetSingleton()).IsExistFile(pTex1))
            continue;
        const char* pTex2 = SKY_TEXTURE(row, 1);
        if (pTex2 && (!*pTex2 || !(CVFSManager::GetSingleton()).IsExistFile(pTex2)))
            pTex2 = NULL;
        PinSkyTextures(hShader, (short)row, pTex1, pTex2);
        ++warmed;
    }
    ::setDelayedLoad(2);
    ::doLogf("sky: built and pinned %d skies in %lu ms\n", warmed, (unsigned long)(timeGetTime() - start));
}

//-------------------------------------------------------------------------------------------------
CSkyDOME::CSkyDOME(HNODE hShader, HNODE hLight, short nSkyIDX):
    m_nSkyIDX(nSkyIDX), m_hSKY(NULL), m_hMESH(NULL), m_hMAT(NULL) {
    char *pZmsName, *pMatName, *pTexName1 = NULL, *pTexName2 = NULL;

    pZmsName = CStr::Printf("__XXX_sky_me");
    if ((CVFSManager::GetSingleton()).IsExistFile(SKY_MESH(nSkyIDX)) == false) {
        pZmsName = CStr::Printf("[ %s ] file open error ...", SKY_MESH(nSkyIDX));
        g_pCApp->ErrorBOX(pZmsName, "ERROR");
    }

    pMatName = CStr::Printf("__XXX_sky_ma");
    if ((CVFSManager::GetSingleton()).IsExistFile(SKY_TEXTURE(nSkyIDX, 0))) {
        pTexName1 = SKY_TEXTURE(nSkyIDX, 0);
    } else {
        pTexName1 = CStr::Printf("[ %s ] file open error ...", SKY_TEXTURE(nSkyIDX, 0));
        g_pCApp->ErrorBOX(pTexName1, "ERROR", MB_OK);
        return;
    }

    if ((CVFSManager::GetSingleton()).IsExistFile(SKY_TEXTURE(nSkyIDX, 1))) {
        pTexName2 = SKY_TEXTURE(nSkyIDX, 1);
    }

    m_hMESH = ::loadMesh(pZmsName, SKY_MESH(nSkyIDX));
    if (m_hMESH) {
        m_hMAT = ::loadSkyMaterial(pMatName, hShader, pTexName1, pTexName2);
        PinSkyTextures(hShader, nSkyIDX, pTexName1, pTexName2);
    }

    ::setSkyMaterialBlendRatio(m_hMAT, 1.0f);

    // --- 첫번째 하늘 메쉬와 재질 생성. (제일 먼거리에 있는 것부터 생성)
    // --- 하늘 오브젝트 생성(loadVisible() 과 사용법 동일)
    ::setMaterialUseAlpha(m_hMAT, 0);

    m_hSKY = ::loadSky("__XXX_sky", m_hMESH, m_hMAT, hLight);
    ::setScale(m_hSKY, 1.0, 1.0, 1.0);

    // --- 두번째 하늘 메쉬와 재질 생성
    ::setMaterialUseAlpha(m_hMAT, 1);
    // --- 메쉬와 재질 생성 후 하늘 오브젝트에 등록시킴
    ::addRenderUnit(m_hSKY, m_hMESH, m_hMAT, hLight);

    ::setMaterialUseAlphaTest(m_hMAT, 0);

    // --- 하늘 오브젝트는 포그의 영향을 받지 말아야 하므로, 아래와 같이 세팅
    ::setReceiveFog(m_hSKY, 0);

    // --- 각 렌더유닛들의 회전 속도 지정
    // --- 회전 축은 월드의 z 축.
    // --- 두번째 인자: 렌더유닛 번호(0부터 시작)
    // --- 세번째 인자: 회전 방향 및 속도. 음수 가능. 초당 회전 각도의 단위
    /*
    ::setSkyRotationSpeed( m_hSKY, 0, 2 );
    ::setSkyRotationSpeed( m_hSKY, 1, 1 );
    ::setSkyRotationSpeed( m_hSKY, 2, 0.5 );
    */
}

//-------------------------------------------------------------------------------------------------
CSkyDOME::~CSkyDOME() {
    if (m_hMAT)
        ::unloadMaterial(m_hMAT);
    if (m_hMESH)
        ::unloadMesh(m_hMESH);

    if (m_hSKY)
        ::unloadSky(m_hSKY);
}

//-------------------------------------------------------------------------------------------------
bool
CSkyDOME::Init(HNODE hShader, HNODE hLight, short nSkyIDX) {
    if (m_pInstance) {
        if (m_pInstance->GetSkyIDX() == nSkyIDX)
            return true;

        SAFE_DELETE(m_pInstance);
    }

    m_pInstance = new CSkyDOME(hShader, hLight, nSkyIDX);
    return (m_pInstance != NULL);
}

//-------------------------------------------------------------------------------------------------
