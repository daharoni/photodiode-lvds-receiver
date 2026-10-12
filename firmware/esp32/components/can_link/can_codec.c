/* can_codec.c - see can_codec.h. Pure C, little endian on the wire (protocol s.1). */
#include "can_codec.h"
#include <string.h>

static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *p, uint32_t v) { put16(p, (uint16_t)v); put16(p + 2, (uint16_t)(v >> 16)); }
static uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t get32(const uint8_t *p) { return (uint32_t)get16(p) | ((uint32_t)get16(p + 2) << 16); }

uint16_t can_id_pack(uint8_t cls, uint8_t func, uint8_t node)
{
    return (uint16_t)(((cls & 7u) << 8) | ((func & 15u) << 4) | (node & 15u)); /* s.1.1 */
}

bool can_id_unpack(uint32_t id, uint8_t *cls, uint8_t *func, uint8_t *node)
{
    if (id > 0x7FFu) {
        return false;
    }
    *cls = (uint8_t)((id >> 8) & 7u);
    *func = (uint8_t)((id >> 4) & 15u);
    *node = (uint8_t)(id & 15u);
    return true;
}

uint8_t can_get_encode(uint16_t param, uint8_t out[8])
{
    memset(out, 0, 8);
    put16(out, param);
    return 2;
}

bool can_get_decode(const uint8_t *d, uint8_t dlc, uint16_t *param)
{
    if (dlc != 2) {
        return false;
    }
    *param = get16(d);
    return true;
}

uint8_t can_set_encode(uint16_t param, int32_t value, uint8_t out[8])
{
    memset(out, 0, 8);
    put16(out, param);
    put32(out + 2, (uint32_t)value);
    return 6;
}

bool can_set_decode(const uint8_t *d, uint8_t dlc, uint16_t *param, int32_t *value)
{
    if (dlc != 6) {
        return false;
    }
    *param = get16(d);
    *value = (int32_t)get32(d + 2);
    return true;
}

uint8_t can_reply_encode(uint16_t param, uint8_t status, int32_t value, uint8_t out[8])
{
    memset(out, 0, 8);
    put16(out, param);
    out[2] = status;
    put32(out + 3, (uint32_t)value);
    return 7;
}

bool can_reply_decode(const uint8_t *d, uint8_t dlc, uint16_t *param, uint8_t *status, int32_t *value)
{
    if (dlc != 7) {
        return false;
    }
    *param = get16(d);
    *status = d[2];
    *value = (int32_t)get32(d + 3);
    return true;
}

bool can_identify_decode(const uint8_t *d, uint8_t dlc, uint8_t *seconds)
{
    if (dlc != 1) {
        return false;
    }
    *seconds = d[0];
    return true;
}

bool can_link_all_decode(const uint8_t *d, uint8_t dlc, can_link_all_t *out)
{
    if (dlc != 8) {
        return false;
    }
    /* s.1.5: node n in byte (n-1)/2, low nibble for odd n, high for even n */
    for (int n = 1; n <= 14; n++) {
        uint8_t b = d[(n - 1) / 2];
        out->nibble[n - 1] = (n & 1) ? (b & 0x0F) : (b >> 4);
    }
    out->seq = d[7];
    return true;
}

uint8_t can_link_all_encode(const can_link_all_t *in, uint8_t out[8])
{
    memset(out, 0, 8);
    for (int n = 1; n <= 14; n++) {
        uint8_t v = in->nibble[n - 1] & 0x0F;
        out[(n - 1) / 2] |= (n & 1) ? v : (uint8_t)(v << 4);
    }
    out[7] = in->seq;
    return 8;
}

uint8_t can_link_all_nibble(const can_link_all_t *l, uint8_t node)
{
    if (node < 1 || node > 14) {
        return 0xFF;
    }
    return l->nibble[node - 1];
}

uint8_t can_tlm_analog_encode(const can_tlm_analog_t *t, uint8_t out[8])
{
    put16(out, t->hv_dv);
    put16(out + 2, t->rssi_mv);
    put16(out + 4, t->vth_mv);
    put16(out + 6, t->m_x10);
    return 8;
}

bool can_tlm_analog_decode(const uint8_t *d, uint8_t dlc, can_tlm_analog_t *t)
{
    if (dlc != 8) {
        return false;
    }
    t->hv_dv = get16(d);
    t->rssi_mv = get16(d + 2);
    t->vth_mv = get16(d + 4);
    t->m_x10 = get16(d + 6);
    return true;
}

uint8_t can_tlm_state_encode(const can_tlm_state_t *t, uint8_t out[8])
{
    out[0] = (uint8_t)((t->hv_state & 7u) | (t->tia_20k ? 1u << 3 : 0) | (t->bus_mode ? 1u << 4 : 0) |
                       (t->comp_en ? 1u << 5 : 0) | (t->link_valid ? 1u << 6 : 0) | (t->tia_auto ? 1u << 7 : 0));
    out[1] = t->loop_state;
    put16(out + 2, t->faults);
    put16(out + 4, t->dac_hv);
    out[6] = t->link_err & 7u;
    out[7] = (uint8_t)((t->selftest_last & 3u) | (t->aux_in ? 1u << 2 : 0) | ((t->src & 3u) << 3));
    return 8;
}

bool can_tlm_state_decode(const uint8_t *d, uint8_t dlc, can_tlm_state_t *t)
{
    if (dlc != 8) {
        return false;
    }
    t->hv_state = d[0] & 7u;
    t->tia_20k = (d[0] >> 3) & 1u;
    t->bus_mode = (d[0] >> 4) & 1u;
    t->comp_en = (d[0] >> 5) & 1u;
    t->link_valid = (d[0] >> 6) & 1u;
    t->tia_auto = (d[0] >> 7) & 1u;
    t->loop_state = d[1];
    t->faults = get16(d + 2);
    t->dac_hv = get16(d + 4);
    t->link_err = d[6] & 7u;
    t->selftest_last = d[7] & 3u;
    t->aux_in = (d[7] >> 2) & 1u;
    t->src = (d[7] >> 3) & 3u;
    return true;
}

uint8_t can_tlm_slow_encode(const can_tlm_slow_t *t, uint8_t out[8])
{
    put32(out, t->uptime_s);
    put16(out + 4, (uint16_t)t->temp_dc);
    out[6] = t->tec;
    out[7] = t->rec;
    return 8;
}

bool can_tlm_slow_decode(const uint8_t *d, uint8_t dlc, can_tlm_slow_t *t)
{
    if (dlc != 8) {
        return false;
    }
    t->uptime_s = get32(d);
    t->temp_dc = (int16_t)get16(d + 4);
    t->tec = d[6];
    t->rec = d[7];
    return true;
}

uint8_t can_fault_event_encode(const can_fault_event_t *e, uint8_t out[8])
{
    put16(out, e->faults);
    put16(out + 2, e->new_faults);
    out[4] = e->hv_state;
    out[5] = e->loop_state;
    out[6] = e->reset_reason;
    out[7] = 0;
    return 8;
}

bool can_fault_event_decode(const uint8_t *d, uint8_t dlc, can_fault_event_t *e)
{
    if (dlc != 8) {
        return false;
    }
    e->faults = get16(d);
    e->new_faults = get16(d + 2);
    e->hv_state = d[4];
    e->loop_state = d[5];
    e->reset_reason = d[6];
    return true;
}

uint8_t can_boot_encode(const can_boot_t *b, uint8_t out[8])
{
    memset(out, 0, 8);
    out[0] = b->reset_reason;
    out[1] = b->fw_major;
    out[2] = b->fw_minor;
    out[3] = b->fw_patch;
    out[4] = b->node;
    return 8;
}

bool can_boot_decode(const uint8_t *d, uint8_t dlc, can_boot_t *b)
{
    if (dlc != 8) {
        return false;
    }
    b->reset_reason = d[0];
    b->fw_major = d[1];
    b->fw_minor = d[2];
    b->fw_patch = d[3];
    b->node = d[4];
    return true;
}

uint8_t can_selftest_encode(const can_selftest_t *s, uint8_t out[8])
{
    memset(out, 0, 8);
    out[0] = s->pass;
    out[1] = s->steps_run;
    put16(out + 2, s->fail_mask);
    put16(out + 4, s->hv_peak_dv);
    return 8;
}

bool can_selftest_decode(const uint8_t *d, uint8_t dlc, can_selftest_t *s)
{
    if (dlc != 8) {
        return false;
    }
    s->pass = d[0];
    s->steps_run = d[1];
    s->fail_mask = get16(d + 2);
    s->hv_peak_dv = get16(d + 4);
    return true;
}

uint16_t can_crc16(const uint8_t *d, size_t n)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint16_t)(d[i] << 8);
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

uint8_t can_enum_slot(const uint8_t mac[6]) { return (uint8_t)(can_crc16(mac, 6) % 64u); }
uint8_t can_enum_hash4(const uint8_t mac[6]) { return (uint8_t)(can_crc16(mac, 6) & 0x0Fu); }

bool can_enum_req_decode(const uint8_t *d, uint8_t dlc, uint8_t *round, uint8_t *slot_ms)
{
    if (dlc != 2) {
        return false;
    }
    *round = d[0];
    *slot_ms = d[1];
    return true;
}

uint8_t can_enum_announce_encode(const uint8_t mac[6], uint8_t node, uint8_t fw_major, uint8_t fw_minor, uint8_t out[8])
{
    memcpy(out, mac, 6);
    out[6] = node;
    out[7] = (uint8_t)(((fw_major & 15u) << 4) | (fw_minor & 15u));
    return 8;
}

bool can_enum_announce_decode(const uint8_t *d, uint8_t dlc, uint8_t mac[6], uint8_t *node, uint8_t *fw)
{
    if (dlc != 8) {
        return false;
    }
    memcpy(mac, d, 6);
    *node = d[6];
    *fw = d[7];
    return true;
}

uint8_t can_enum_assign_encode(const uint8_t mac[6], uint8_t node, uint8_t flags, uint8_t out[8])
{
    memcpy(out, mac, 6);
    out[6] = node;
    out[7] = flags;
    return 8;
}

bool can_enum_assign_decode(const uint8_t *d, uint8_t dlc, uint8_t mac[6], uint8_t *node, uint8_t *flags)
{
    if (dlc != 8) {
        return false;
    }
    memcpy(mac, d, 6);
    *node = d[6];
    *flags = d[7];
    return true;
}
