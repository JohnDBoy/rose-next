#ifndef _CBank_
#define _CBank_

#include "../gamecommon/CObservable.h"
#include "citem.h"

#include <map>
const int g_iSlotCountPerPage = 40; ///페이지당 슬롯 갯수
const int g_iPageCount = 4;
class CItem;

/**
 * 계정창고에 대한 데이타 Class
 *	- 싱글톤
 *	- Observer : CBankDlg
 *
 * @Author		최종진
 * @Date			2005/9/15
 */
class CBank: public CObservable {
    CBank(void);

public:
    static CBank& GetInstance();
    ~CBank(void);

    void SetItem(int iIndex, tagITEM& Item);
    void ClearItems();
    void SetNpcClientIndex(int iIndex);
    int GetNpcClientIndex();
    bool HasEmptySlot(bool bPlatinum);
    void SetMoney(__int64 money);
    __int64 GetMoney();
    void SetAccountStorage(bool bAccountStorage) { m_bAccountStorage = bAccountStorage; }
    bool IsAccountStorage() const { return m_bAccountStorage; }

private:
    std::map<int, CItem*> m_Items;

    int m_iNpcClientIndex;
    __int64 m_Money;
    bool m_bAccountStorage;

    // CItem* CreateItem( tagITEM& Item );
};
#endif