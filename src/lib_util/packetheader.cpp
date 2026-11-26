
#include <windows.h>
#include "PacketHEADER.h"
#include "util/classstr.h"

struct t_PACKET;

//---------------------------------------------------------------------------
// A text inside a packet, bounded by the packet's own size (2026-11-26, after EVO-REFORGED
// 967a7c5e). The two-argument reader ran strlen with no bound, so a text without its end
// inside the packet -- a malformed client packet, on the server -- was read on into the
// receive buffer behind it. Such a text is now cut at the packet's last byte (written as
// the end) rather than refused: not every caller checks for NULL.
static char*
Packet_StrAt(t_PACKET* pPacket, short& nOffset, short& nOutStrLEN) {
    t_PACKETHEADER* pHeader = (t_PACKETHEADER*)pPacket;
    const int iSize = pHeader->m_nSize;
    if (nOffset < 0 || nOffset >= iSize || iSize > (int)MAX_PACKET_SIZE) {
        return NULL;
    }

    char* pStr = (char*)pHeader->m_pDATA + nOffset;
    const char* pEnd = (const char*)memchr(pStr, 0, (size_t)(iSize - nOffset));
    if (!pEnd) {
        OutputDebugString("Error !! Packet_GetStringPtr.. a text without its end inside the packet\n");
        pHeader->m_pDATA[iSize - 1] = '\0';
        pEnd = (const char*)pHeader->m_pDATA + iSize - 1;
    }

    nOutStrLEN = (short)(pEnd - pStr);
    nOffset = (short)(nOffset + nOutStrLEN + 1);
    return pStr;
}

//---------------------------------------------------------------------------
char*
Packet_GetStringPtr(t_PACKET* pPacket, short& nOffset, short& nOutStrLEN) {
    return Packet_StrAt(pPacket, nOffset, nOutStrLEN);
}

//---------------------------------------------------------------------------
char*
Packet_GetStringPtr(t_PACKET* pPacket, short& nOffset) {
    short nStrLEN;
    return Packet_StrAt(pPacket, nOffset, nStrLEN);
}

//---------------------------------------------------------------------------
void*
Packet_GetDataPtr(t_PACKET* pPacket, short& nOffset, short nSize) {
    if (nOffset + nSize > ((t_PACKETHEADER*)pPacket)->m_nSize) {
        // iCARUS_LogString (LOG_DEBUG_, "Packet_GetDataPtr return NULL !!! Type: [0x%x], Size:
        // [%d], Offset: [%d]", pPacket->cType, pPacket->m_nSize, *pOffset);
        return NULL;
    }

    char* pData;
    pData = (char*)((t_PACKETHEADER*)pPacket)->m_pDATA + nOffset;
    nOffset += nSize;

    return (void*)pData;
}

//---------------------------------------------------------------------------
bool
Packet_AppendString(t_PACKET* pPacket, char* pStr) {
    short nLen, nSize;

    nLen = (pStr) ? static_cast<short>(strlen(pStr)) + 1 : 1;
    nSize = ((t_PACKETHEADER*)pPacket)->m_nSize;

    if (nSize + nLen >= MAX_PACKET_SIZE) {
        OutputDebugString("Error !! Packet_AppendString.. Too Big Packet\n");
        // iCARUS_LogString (LOG_NORMAL, "Error !! Packet_AppendString[ Too Big Packet, Size:%d ]",
        // nSize+nLen);
        return false;
    }

    if (nLen > 1) {
        CopyMemory(((t_PACKETHEADER*)pPacket)->m_pDATA + nSize, pStr, nLen - 1);
    }

    ((t_PACKETHEADER*)pPacket)->m_pDATA[nSize + nLen - 1] = '\0';

    ((t_PACKETHEADER*)pPacket)->m_nSize += nLen;

    return true;
}

//---------------------------------------------------------------------------
bool
Packet_AppendData(t_PACKET* pPacket, void* pData, int nLen) {
    short nSize;

    if (!pData || !nLen) {
        OutputDebugString("Error !! Packet_AppendData.. Source Data is NULL or Length is 0 \n");
        // iCARUS_LogString (LOG_NORMAL, "Error !! Packet_AppendData[ Source Data is NULL or Length
        // is 0 ]");
        return false;
    }

    nSize = ((t_PACKETHEADER*)pPacket)->m_nSize;
    if (nSize + nLen >= MAX_PACKET_SIZE) {
        OutputDebugString("Error !! Packet_AppendData.. Too Big Packet\n");
        // iCARUS_LogString (LOG_NORMAL, "Error !! Packet_AppendData[ Too Big Packet, Size:%d ]",
        // nSize+nLen);
        return false;
    }

    CopyMemory(((t_PACKETHEADER*)pPacket)->m_pDATA + nSize, pData, nLen);

    ((t_PACKETHEADER*)pPacket)->m_nSize += nLen;

    return true;
}

//---------------------------------------------------------------------------
