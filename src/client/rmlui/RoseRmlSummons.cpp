#include "stdafx.h"

#include "RoseRmlSummons.h"
#include "RoseRmlIcons.h"
#include "RoseRmlLayout.h"
#include "RoseRmlText.h"
#include "RoseUi2.h"

#include <RmlUi/Core/Context.h>
#include <RmlUi/Core/ElementDocument.h>

#include "..\\Game.h"
#include "../CObjUSER.h"
#include "../Object.h"
#include "../JCommandState.h"
#include "../System/CGame.h"
#include "../GameCommon/Skill.h"
#include "../gamecommon/StringManager.h"
#include "../common/IO_AI.h"
#include "../interface/io_imageres.h"

#include "rose/common/log.h"
#include "rose/io/stb.h"

#include <stdio.h>
#include <stdarg.h>

namespace {

Rml::String
Printf(const char* pszFormat, ...) {
    char szBuf[160];
    va_list args;
    va_start(args, pszFormat);
    _vsnprintf(szBuf, sizeof(szBuf), pszFormat, args);
    va_end(args);
    szBuf[sizeof(szBuf) - 1] = '\0';
    return szBuf;
}

void
AddLine(Rml::String& strText, const Rml::String& strLine) {
    if (strLine.empty())
        return;
    if (!strText.empty())
        strText += '\n';
    strText += strLine;
}

/// World units are cm.
int
Metres(int iUnits) {
    return (iUnits + 50) / 100;
}

/// What the skill is, in a few words, from its LIST_SKILL type, reach and area.
/// Written for a summon casting it, so "itself" is the summon.
Rml::String
DescribeKind(int iSkill) {
    const int iDist = Metres(SKILL_DISTANCE(iSkill));
    const int iScope = Metres(SKILL_SCOPE(iSkill));
    const bool bHarm = SKILL_HARM(iSkill) != 0;

    switch (SKILL_TYPE(iSkill)) {
        case SKILL_ACTION_IMMEDIATE:
        case SKILL_ACTION_ENFORCE_WEAPON:
        case SKILL_ACTION_ENFORCE_BULLET:
            return "Melee strike";
        case SKILL_ACTION_FIRE_BULLET:
            return iDist > 0 ? Printf("Ranged attack, %d m", iDist) : Rml::String("Ranged attack");
        case SKILL_ACTION_AREA_TARGET:
            return Printf("Area attack: within %d m of its target", iScope);
        case SKILL_ACTION_SELF_DAMAGE:
            return Printf("Area attack: within %d m of itself", iScope);
        case SKILL_ACTION_SELF_AND_TARGET:
            return "Strikes its target and strengthens itself";
        case SKILL_ACTION_SELF_BOUND_DURATION:
        case SKILL_ACTION_SELF_STATE_DURATION:
        case SKILL_ACTION_SELF_BOUND:
            return iScope > 0 ? Printf("Itself and allies within %d m", iScope)
                              : Rml::String("On itself");
        case SKILL_ACTION_TARGET_BOUND_DURATION:
        case SKILL_ACTION_TARGET_STATE_DURATION:
        case SKILL_ACTION_TARGET_BOUND: {
            Rml::String strKind = bHarm ? "Debuff on an enemy" : "On an ally";
            if (iDist > 0)
                strKind += Printf(", %d m", iDist);
            return strKind;
        }
        default:
            return Rml::String();
    }
}

bool
IsDamageType(int iType) {
    switch (iType) {
        case SKILL_ACTION_IMMEDIATE:
        case SKILL_ACTION_ENFORCE_WEAPON:
        case SKILL_ACTION_ENFORCE_BULLET:
        case SKILL_ACTION_FIRE_BULLET:
        case SKILL_ACTION_AREA_TARGET:
        case SKILL_ACTION_SELF_DAMAGE:
        case SKILL_ACTION_SELF_AND_TARGET:
            return true;
        default:
            return false;
    }
}

/// The tooltip body: kind, power, heals, applied states, then the STL
/// description when the row has one ( most monster skills do not ).
Rml::String
DescribeAbility(int iSkill) {
    Rml::String strText;
    AddLine(strText, DescribeKind(iSkill));

    if (IsDamageType(SKILL_TYPE(iSkill)) && SKILL_POWER(iSkill) > 0)
        AddLine(strText, Printf("Power %d", SKILL_POWER(iSkill)));

    /// Instant HP / MP ( the Bonfires ). The server scales the flat value a
    /// little by the caster's INT ( CCal::Get_SkillAdjustVALUE ): this is the
    /// base.
    Rml::String strRestore;
    for (int i = 0; i < SKILL_INCREASE_ABILITY_CNT; i++) {
        const int iValue = SKILL_INCREASE_ABILITY_VALUE(iSkill, i);
        if (iValue <= 0)
            continue;
        const char* pszWhat = NULL;
        if (SKILL_INCREASE_ABILITY(iSkill, i) == AT_HP)
            pszWhat = "HP";
        else if (SKILL_INCREASE_ABILITY(iSkill, i) == AT_MP)
            pszWhat = "MP";
        if (pszWhat == NULL)
            continue;
        strRestore += Printf(strRestore.empty() ? "Restores %d %s" : ", %d %s", iValue, pszWhat);
    }
    AddLine(strText, strRestore);

    const int iChance = SKILL_SUCCESS_RATIO(iSkill);
    const int iSeconds = SKILL_DURATION(iSkill);
    for (int i = 0; i < 2; i++) {
        const int iState = SKILL_STATE_STB(iSkill, i);
        if (iState <= 0)
            continue;
        const Rml::String strState = RoseRmlText::FromGame(STATE_NAME(iState));
        if (strState.empty())
            continue;
        Rml::String strLine = "Applies " + strState;
        if (iSeconds > 0)
            strLine += Printf(" for %d s", iSeconds);
        if (iChance > 0 && iChance < 100)
            strLine += Printf(", %d%% chance", iChance);
        AddLine(strText, strLine);
    }

    const Rml::String strDesc = RoseRmlText::FromGame(SKILL_DESC(iSkill));
    if (!strDesc.empty()) {
        if (!strText.empty())
            strText += '\n';
        AddLine(strText, strDesc);
    }
    return strText;
}

} // namespace

RoseRmlSummons::RoseRmlSummons():
    m_pContext(NULL), m_pDocument(NULL), m_pPanel(NULL), m_bVisible(false) {}

bool
RoseRmlSummons::Initialise(Rml::Context* pContext, const std::string& strAssetDir) {
    if (pContext == NULL)
        return false;

    m_pContext = pContext;

    Rml::DataModelConstructor constructor = pContext->CreateDataModel("summons");
    if (!constructor)
        return false;

    RoseRmlBuffBar::RegisterBuffStruct(constructor);

    if (auto ability = constructor.RegisterStruct<AbilityVM>()) {
        ability.RegisterMember("src", &AbilityVM::src);
        ability.RegisterMember("rect", &AbilityVM::rect);
        ability.RegisterMember("name", &AbilityVM::name);
        ability.RegisterMember("detail", &AbilityVM::detail);
    }
    constructor.RegisterArray<std::vector<AbilityVM>>();

    if (auto summon = constructor.RegisterStruct<SummonVM>()) {
        summon.RegisterMember("tag", &SummonVM::tag);
        summon.RegisterMember("name", &SummonVM::name);
        summon.RegisterMember("level", &SummonVM::level);
        summon.RegisterMember("hp", &SummonVM::hp);
        summon.RegisterMember("hp_width", &SummonVM::hp_width);
        summon.RegisterMember("hp_low", &SummonVM::hp_low);
        summon.RegisterMember("atk", &SummonVM::atk);
        summon.RegisterMember("def", &SummonVM::def);
        summon.RegisterMember("res", &SummonVM::res);
        summon.RegisterMember("abilities", &SummonVM::abilities);
        summon.RegisterMember("buffs", &SummonVM::buffs);
    }
    constructor.RegisterArray<std::vector<SummonVM>>();

    constructor.Bind("summons", &m_Summons);
    constructor.Bind("capacity", &m_strCapacity);

    /// Click a card: target that summon ( to heal or buff it ).
    constructor.BindEventCallback("target",
        [](Rml::DataModelHandle, Rml::Event&, const Rml::VariantList& args) {
            if (args.empty())
                return;
            const int iClientIdx = args[0].Get<int>();
            if (iClientIdx > 0 && g_pObjMGR->Get_CharOBJ(iClientIdx, true) != NULL)
                g_UserInputSystem.SetCurrentTarget(iClientIdx);
        });

    m_Model = constructor.GetModelHandle();

    const std::string strDoc = strAssetDir + "summons.rml";
    m_pDocument = pContext->LoadDocument(strDoc.c_str());
    if (m_pDocument == NULL) {
        LOG_WARN("[rmlui] could not load summons document '{}'", strDoc.c_str());
        return false;
    }

    m_pPanel = m_pDocument->GetElementById("summons");
    RoseRmlLayout::Track(m_pPanel, "summons");

    LOG_INFO("[rmlui] summons document loaded");
    return true;
}

void
RoseRmlSummons::Shutdown() {
    /// The context owns the document; it is torn down with Rml::Shutdown().
    m_pDocument = NULL;
    m_pContext = NULL;
    m_pPanel = NULL;
    m_bVisible = false;
}

void
RoseRmlSummons::SetVisible(bool bVisible) {
    if (m_pDocument == NULL || bVisible == m_bVisible)
        return;

    m_bVisible = bVisible;
    if (bVisible)
        m_pDocument->Show();
    else
        m_pDocument->Hide();
}

const std::vector<RoseRmlSummons::AbilityVM>&
RoseRmlSummons::AbilitiesOf(int nCharNo) {
    std::map<int, std::vector<AbilityVM>>::iterator it = m_Abilities.find(nCharNo);
    if (it != m_Abilities.end())
        return it->second;

    std::vector<AbilityVM>& abilities = m_Abilities[nCharNo];

    short aSkills[16];
    const int iCount = g_AI_LIST.CollectCastSkills(NPC_AI_TYPE(nCharNo), aSkills, 16);
    for (int i = 0; i < iCount; i++) {
        const int iSkill = aSkills[i];
        if (iSkill >= g_SkillList.Get_SkillCNT())
            continue;

        AbilityVM vm;
        vm.name = RoseRmlText::FromGame(SKILL_NAME(iSkill));
        if (vm.name.empty())
            continue;
        RoseRmlIcons::Resolve(IMAGE_RES_SKILL_ICON, SKILL_ICON_NO(iSkill), vm.src, vm.rect);
        vm.detail = DescribeAbility(iSkill);
        abilities.push_back(vm);
    }
    return abilities;
}

void
RoseRmlSummons::Update() {
    if (m_pDocument == NULL)
        return;

    CObjUSER* pAvatar = g_pAVATAR;
    const bool bInWorld = RoseUi2::IsActive() && pAvatar != NULL
        && CGame::GetInstance().GetCurrStateID() == CGame::GS_MAIN;

    std::vector<SummonVM> summons;
    if (bInWorld) {
        const DWORD dwNow = g_GameDATA.GetGameTime();
        const std::list<SummonMobInfo>& list = pAvatar->GetSummonedMobList();
        for (std::list<SummonMobInfo>::const_iterator it = list.begin(); it != list.end(); ++it) {
            const int iClientIdx = g_pObjMGR->Get_ClientObjectIndex(it->iIndex);
            CObjCHAR* pMob = g_pObjMGR->Get_ClientCharOBJ(it->iIndex, false);
            if (pMob == NULL)
                continue;

            SummonVM vm;
            vm.tag = iClientIdx;
            vm.name = RoseRmlText::FromGame(pMob->Get_NAME());
            vm.level = Printf("%d", it->iSummonLevel);
            vm.atk = it->iAtk;
            vm.def = it->iDef;
            vm.res = it->iRes;

            const int iHp = max(0, pMob->Get_HP());
            const int iMaxHp = pMob->Get_MaxHP();
            const float fPct =
                (iMaxHp > 0) ? 100.0f * (float)min(iHp, iMaxHp) / (float)iMaxHp : 0.0f;
            vm.hp = Printf("%d / %d", iHp, iMaxHp);
            vm.hp_low = fPct < 25.0f;
            RoseRmlEasedBar& bar = m_HpBars[iClientIdx];
            bar.Step(fPct, dwNow);
            vm.hp_width = bar.fShown;

            vm.abilities = AbilitiesOf(pMob->Get_CharNO());
            /// Every summon carries the life-timer state; it tells the player nothing.
            RoseRmlBuffBar::CollectBuffs(pMob, vm.buffs, ING_DEC_LIFE_TIME);
            summons.push_back(vm);
        }
    }

    /// Forget the bars of summons that are gone, so a new summon reusing the
    /// object slot starts full rather than sliding from the old one's HP.
    for (std::map<int, RoseRmlEasedBar>::iterator it = m_HpBars.begin(); it != m_HpBars.end();) {
        bool bLive = false;
        for (size_t i = 0; i < summons.size() && !bLive; i++)
            bLive = (summons[i].tag == it->first);
        if (bLive)
            ++it;
        else
            it = m_HpBars.erase(it);
    }

    if (summons != m_Summons) {
        m_Summons.swap(summons);
        m_Model.DirtyVariable("summons");
    }

    Rml::String strCapacity;
    if (bInWorld && pAvatar->GetCur_SummonMaxCapacity() > 0)
        strCapacity = Printf("%d / %d", pAvatar->GetCur_SummonUsedCapacity(),
            pAvatar->GetCur_SummonMaxCapacity());
    if (strCapacity != m_strCapacity) {
        m_strCapacity = strCapacity;
        m_Model.DirtyVariable("capacity");
    }

    SetVisible(!m_Summons.empty());

    if (m_bVisible) {
        const Rml::Vector2i view = m_pContext->GetDimensions();
        RoseRmlLayout::Clamp(m_pPanel, view.x, view.y);
    }
}
