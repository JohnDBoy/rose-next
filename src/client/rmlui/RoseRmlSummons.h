#ifndef _ROSE_RML_SUMMONS_H_
#define _ROSE_RML_SUMMONS_H_

/**
 * UI2 summon cards ( RoseUi2::PIECE_SUMMON_PANEL ), replacing CSummonInfoPanel:
 * one card per summon you own -- name, level, HP, the scaled ATK / DEF / RES,
 * what it can cast, and its status effects ( less the life timer every summon
 * carries ). Shown only while you own one.
 *
 * Abilities are read from the summon's AI file ( LIST_NPC col 16 -> its .aip ),
 * whose "cast a skill" actions ( AIACT_24 ) are everything a summon ever casts
 * besides its plain attack -- no table lists them. The tooltip is written from
 * the skill row ( kind, reach, power, heals, the status it applies ) because
 * most monster skills have no description, and the classic skill tooltip would
 * list learning requirements that mean nothing for a summon.
 *
 * The stats are the ones cached at summon time ( SummonMobInfo, the server's
 * CObjSUMMON::SetCallerOBJ scaling ), as the classic panel showed them; HP and
 * status are read live. Click a card to target the summon.
 *
 * Read-only against game state, except that targeting. Draggable by its title
 * bar; the spot is saved.
 */

#include <RmlUi/Core/DataModelHandle.h>
#include <RmlUi/Core/Types.h>

#include <map>
#include <string>
#include <vector>

#include "RoseRmlBuffBar.h"
#include "RoseRmlEasedBar.h"

struct SummonMobInfo;

namespace Rml {
class Context;
class Element;
class ElementDocument;
} // namespace Rml

class RoseRmlSummons {
public:
    struct AbilityVM {
        Rml::String src;
        Rml::String rect;
        Rml::String name;
        Rml::String detail; ///< one fact per line ( the tip body is pre-line )

        bool operator==(const AbilityVM& o) const {
            return src == o.src && rect == o.rect && name == o.name && detail == o.detail;
        }
        bool operator!=(const AbilityVM& o) const { return !(*this == o); }
    };

    struct SummonVM {
        int tag; ///< client object index, for the click
        Rml::String name;
        Rml::String level;
        Rml::String hp; ///< "cur / max"
        float hp_width; ///< eased, 0..100
        bool hp_low;
        int atk;
        int def;
        int res;
        std::vector<AbilityVM> abilities;
        std::vector<RoseRmlBuffBar::BuffVM> buffs;

        SummonVM(): tag(0), hp_width(0.0f), hp_low(false), atk(0), def(0), res(0) {}

        bool operator==(const SummonVM& o) const {
            return tag == o.tag && name == o.name && level == o.level && hp == o.hp
                && hp_width == o.hp_width && hp_low == o.hp_low && atk == o.atk && def == o.def
                && res == o.res && abilities == o.abilities && buffs == o.buffs;
        }
        bool operator!=(const SummonVM& o) const { return !(*this == o); }
    };

    RoseRmlSummons();

    bool Initialise(Rml::Context* pContext, const std::string& strAssetDir);
    void Shutdown();

    /// Per frame: samples every owned summon and dirties the model on change.
    void Update();

private:
    void SetVisible(bool bVisible);

    /// The abilities of LIST_NPC row nCharNo, built once per row.
    const std::vector<AbilityVM>& AbilitiesOf(int nCharNo);

    Rml::Context* m_pContext;
    Rml::ElementDocument* m_pDocument;
    Rml::Element* m_pPanel;
    Rml::DataModelHandle m_Model;
    bool m_bVisible;

    std::map<int, RoseRmlEasedBar> m_HpBars; ///< by client object index
    std::map<int, std::vector<AbilityVM>> m_Abilities; ///< by LIST_NPC row

    /// --- bound to summons.rml ------------------------------------------------
    std::vector<SummonVM> m_Summons;
    Rml::String m_strCapacity; ///< "used / max" summon gauge, empty if unknown
};

#endif /// _ROSE_RML_SUMMONS_H_
