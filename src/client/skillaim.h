#pragma once

#include <d3dx9math.h>

/// Ground aiming for the player's area skills (2026-10-19). A skill that lands somewhere
/// other than on its caster -- type 7, SKILL_ACTION_AREA_TARGET: Arrow Shower, Luna Stone,
/// Ice Bang, Star Gazer, Shadow Servant, Exceed Break -- no longer needs a targeted monster:
/// pressing it shows its area on the ground under the mouse, and a left click casts it
/// there. Skills centred on the caster (type 17: Wind Storm, Spin Attack...) are unchanged.
///
/// - The spot is clamped to the skill's range (SKILL_DISTANCE, a little short of it): the
///   area stops at the range rather than walking the player into range, so what the
///   preview shows is where it lands, now. A strip or cone (Exceed Break) points from the
///   player toward the mouse.
/// - Pressing the same skill again puts it away; pressing another skill cancels it (and
///   runs that one); a right click without a drag (a drag turns the camera), Esc, death
///   and a zone change cancel it.
/// - The skill's usual checks (cooldown, MP, state) run at the key press, so a skill that
///   cannot be cast says so at once, and again at the click (FireSkill).
/// - The cast is CLI_POSITION_SKILL with the spot, which the server already took from any
///   position (SetCMD_Skill2POS); before this it was always the targeted monster's.
///
/// The preview is drawn by CGroundTelegraphs (the same ground overlay as the boss
/// telegraphs), in a friendly colour, with a faint ring at the skill's range.
class CSkillAim {
public:
    static CSkillAim& Instance();

    /// CSkillCommand::Execute: the skill in iSkillSlot was pressed. True when aiming took
    /// the press (began, switched, or was put away); false lets it run as before.
    bool OnSkillPressed(int iSkillSlot);
    bool IsAiming() const { return m_iSlot >= 0; }
    void Cancel();

    /// Per frame, before CGroundTelegraphs::Update (CObjectMANAGER::ProcOBJECT).
    void Update();

    /// CGameStateMain::ProcMouseInput, after the UI had its look: true = consumed.
    bool OnLeftClick();
    bool OnRightDown(int x, int y);
    bool OnRightUp(int x, int y);

private:
    CSkillAim() {}
    bool StillValid() const;
    bool MouseOnGround(D3DXVECTOR3& out) const;
    void ClampToRange(D3DXVECTOR3& aim) const;

    int m_iSlot = -1;
    short m_nSkillIDX = 0;
    bool m_bHaveAim = false;
    D3DXVECTOR3 m_PosAIM = D3DXVECTOR3(0.f, 0.f, 0.f);
    bool m_bRightDown = false;
    int m_iRightX = 0, m_iRightY = 0;
};
