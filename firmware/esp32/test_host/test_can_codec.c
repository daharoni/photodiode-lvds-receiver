#include "test_harness.h"
#include "can_codec.h"

TEST(id_roundtrip_all)
{
    int n = 0;
    for (int cls = 0; cls < 8; cls++)
        for (int fn = 0; fn < 16; fn++)
            for (int node = 0; node < 16; node++) {
                uint16_t id = can_id_pack(cls, fn, node);
                uint8_t c, f, nd;
                ASSERT_TRUE(id <= 0x7FF);
                ASSERT_TRUE(can_id_unpack(id, &c, &f, &nd));
                ASSERT_TRUE(c == cls && f == fn && nd == node);
                n++;
            }
    ASSERT_EQ(n, 2048);
    uint8_t c, f, nd;
    ASSERT_TRUE(!can_id_unpack(0x800, &c, &f, &nd));
}

TEST(id_known_values_from_protocol_table)
{
    ASSERT_EQ(can_id_pack(CAN_CLS_EVENT, CAN_FN_FAULT_EVENT, 3), 0x003);
    ASSERT_EQ(can_id_pack(CAN_CLS_EVENT, CAN_FN_BOOT, 3), 0x013);
    ASSERT_EQ(can_id_pack(CAN_CLS_CMD, CAN_FN_GET, 5), 0x105);
    ASSERT_EQ(can_id_pack(CAN_CLS_CMD, CAN_FN_SET, 5), 0x115);
    ASSERT_EQ(can_id_pack(CAN_CLS_CMD, CAN_FN_IDENTIFY, 5), 0x125);
    ASSERT_EQ(can_id_pack(CAN_CLS_CMD, CAN_FN_LINK_ALL, 0), 0x1F0);
    ASSERT_EQ(can_id_pack(CAN_CLS_RESP, CAN_FN_REPLY, 5), 0x205);
    ASSERT_EQ(can_id_pack(CAN_CLS_RESP, CAN_FN_SELFTEST, 5), 0x215);
    ASSERT_EQ(can_id_pack(CAN_CLS_TLM, CAN_FN_TLM_ANALOG, 14), 0x30E);
    ASSERT_EQ(can_id_pack(CAN_CLS_TLM, CAN_FN_TLM_STATE, 14), 0x31E);
    ASSERT_EQ(can_id_pack(CAN_CLS_TLM, CAN_FN_TLM_SLOW, 14), 0x32E);
    ASSERT_EQ(can_id_pack(CAN_CLS_ENUM, CAN_FN_ENUM_REQ, 15), 0x70F);
    ASSERT_EQ(can_id_pack(CAN_CLS_ENUM, CAN_FN_ENUM_ANNOUNCE, 2), 0x712);
    ASSERT_EQ(can_id_pack(CAN_CLS_ENUM, CAN_FN_ENUM_NEW, 9), 0x729);
    ASSERT_EQ(can_id_pack(CAN_CLS_ENUM, CAN_FN_ENUM_ASSIGN, 15), 0x73F);
}

TEST(link_all_decode)
{
    /* node 1 (low nibble byte0) = valid, class 0 -> 0x8; node 2 (high) = class 3 invalid -> 0x3;
       node 3 low byte1 = valid class 7 -> 0xF; node 14 high byte6 = valid class 2 -> 0xA */
    uint8_t d[8] = {0x38, 0x0F, 0, 0, 0, 0, 0xA0, 0x42};
    can_link_all_t l;
    ASSERT_TRUE(can_link_all_decode(d, 8, &l));
    ASSERT_EQ(can_link_all_nibble(&l, 1), 0x8);
    ASSERT_EQ(can_link_all_nibble(&l, 2), 0x3);
    ASSERT_EQ(can_link_all_nibble(&l, 3), 0xF);
    ASSERT_EQ(can_link_all_nibble(&l, 14), 0xA);
    ASSERT_EQ(can_link_all_nibble(&l, 0), 0xFF);
    ASSERT_EQ(can_link_all_nibble(&l, 15), 0xFF);
    ASSERT_TRUE(CAN_NIBBLE_VALID(0x8) && CAN_NIBBLE_CLASS(0xF) == 7 && CAN_NIBBLE_VALID(0xF));
    ASSERT_TRUE(!CAN_NIBBLE_VALID(0x3));
    ASSERT_EQ(l.seq, 0x42);
    ASSERT_TRUE(!can_link_all_decode(d, 7, &l));
    uint8_t e[8];
    ASSERT_EQ(can_link_all_encode(&l, e), 8);
    ASSERT_TRUE(memcmp(d, e, 8) == 0);
}

TEST(get_set_reply_roundtrip)
{
    uint8_t b[8];
    uint16_t p;
    int32_t v;
    uint8_t st;
    ASSERT_EQ(can_get_encode(0x0013, b), 2);
    ASSERT_EQ(b[0], 0x13); ASSERT_EQ(b[1], 0x00);
    ASSERT_TRUE(can_get_decode(b, 2, &p) && p == 0x0013);
    ASSERT_TRUE(!can_get_decode(b, 3, &p));

    ASSERT_EQ(can_set_encode(0x0012, 1423, b), 6);
    ASSERT_EQ(b[2], 0x8F); ASSERT_EQ(b[3], 0x05);   /* 1423 = 0x058F little endian */
    ASSERT_TRUE(can_set_decode(b, 6, &p, &v) && p == 0x0012 && v == 1423);
    ASSERT_EQ(can_set_encode(0x0012, -2, b), 6);
    ASSERT_TRUE(can_set_decode(b, 6, &p, &v) && v == -2);
    ASSERT_TRUE(!can_set_decode(b, 5, &p, &v));

    ASSERT_EQ(can_reply_encode(0x0023, CAN_ST_RANGE, -41, b), 7);
    ASSERT_TRUE(can_reply_decode(b, 7, &p, &st, &v) && p == 0x0023 && st == CAN_ST_RANGE && v == -41);
    ASSERT_TRUE(!can_reply_decode(b, 6, &p, &st, &v));
    uint8_t s;
    uint8_t i[1] = {30};
    ASSERT_TRUE(can_identify_decode(i, 1, &s) && s == 30);
}

TEST(fault_event_encode)
{
    can_fault_event_t e = {.faults = 0x0801, .new_faults = 0x0800, .hv_state = 4, .loop_state = 6, .reset_reason = 4};
    uint8_t b[8];
    ASSERT_EQ(can_fault_event_encode(&e, b), 8);
    ASSERT_EQ(b[0], 0x01); ASSERT_EQ(b[1], 0x08); ASSERT_EQ(b[2], 0x00); ASSERT_EQ(b[3], 0x08);
    ASSERT_EQ(b[4], 4); ASSERT_EQ(b[5], 6); ASSERT_EQ(b[6], 4); ASSERT_EQ(b[7], 0);
    can_fault_event_t d;
    ASSERT_TRUE(can_fault_event_decode(b, 8, &d));
    ASSERT_TRUE(d.faults == e.faults && d.new_faults == e.new_faults && d.hv_state == 4 && d.loop_state == 6 && d.reset_reason == 4);
}

TEST(boot_and_selftest_frames)
{
    uint8_t b[8];
    can_boot_t bt = {.reset_reason = 1, .fw_major = 0, .fw_minor = 1, .fw_patch = 0, .node = 7}, bd;
    can_boot_encode(&bt, b);
    ASSERT_TRUE(can_boot_decode(b, 8, &bd) && bd.node == 7 && bd.fw_minor == 1 && bd.reset_reason == 1);
    can_selftest_t st = {.pass = 1, .steps_run = 9, .fail_mask = 0x0004, .hv_peak_dv = 1004}, sd;
    can_selftest_encode(&st, b);
    ASSERT_EQ(b[2], 0x04);
    ASSERT_TRUE(can_selftest_decode(b, 8, &sd) && sd.hv_peak_dv == 1004 && sd.fail_mask == 4 && sd.steps_run == 9);
}

TEST(telemetry_frames)
{
    uint8_t b[8];
    can_tlm_analog_t a = {.hv_dv = 1423, .rssi_mv = 1923, .vth_mv = 1651, .m_x10 = 0xFFFF}, ad;
    can_tlm_analog_encode(&a, b);
    ASSERT_TRUE(can_tlm_analog_decode(b, 8, &ad) && ad.hv_dv == 1423 && ad.rssi_mv == 1923 && ad.vth_mv == 1651 && ad.m_x10 == 0xFFFF);
    can_tlm_state_t s = {.hv_state = 2, .tia_20k = true, .bus_mode = true, .comp_en = true, .link_valid = true,
                         .tia_auto = true, .loop_state = 3, .faults = 0x1000, .dac_hv = 2310, .link_err = 5,
                         .selftest_last = 1, .aux_in = true, .src = 2}, sd;
    can_tlm_state_encode(&s, b);
    ASSERT_EQ(b[0], 0xFA);   /* 010 | tia 8 | bus 0x10 | comp 0x20 | valid 0x40 | auto 0x80 */
    ASSERT_EQ(b[7], 0x01 | 0x04 | (2 << 3));
    ASSERT_TRUE(can_tlm_state_decode(b, 8, &sd));
    ASSERT_TRUE(sd.hv_state == 2 && sd.tia_20k && sd.bus_mode && sd.comp_en && sd.link_valid && sd.tia_auto);
    ASSERT_TRUE(sd.loop_state == 3 && sd.faults == 0x1000 && sd.dac_hv == 2310 && sd.link_err == 5);
    ASSERT_TRUE(sd.selftest_last == 1 && sd.aux_in && sd.src == 2);
    can_tlm_slow_t sl = {.uptime_s = 0x01020304, .temp_dc = -123, .tec = 9, .rec = 8}, sld;
    can_tlm_slow_encode(&sl, b);
    ASSERT_EQ(b[0], 4);
    ASSERT_TRUE(can_tlm_slow_decode(b, 8, &sld) && sld.uptime_s == 0x01020304 && sld.temp_dc == -123 && sld.tec == 9 && sld.rec == 8);
}

TEST(enumeration_frames)
{
    uint8_t mac[6] = {0x60, 0x55, 0xF9, 0x01, 0x02, 0x03}, b[8], m2[6], node, x;
    ASSERT_TRUE(can_enum_slot(mac) < 64);
    ASSERT_TRUE(can_enum_hash4(mac) < 16);
    ASSERT_EQ(can_enum_slot(mac), can_crc16(mac, 6) % 64);
    /* CRC-16/CCITT-FALSE check value of "123456789" is 0x29B1 */
    ASSERT_EQ(can_crc16((const uint8_t *)"123456789", 9), 0x29B1);
    can_enum_announce_encode(mac, 0, 0, 1, b);
    ASSERT_EQ(b[7], 0x01);
    ASSERT_TRUE(can_enum_announce_decode(b, 8, m2, &node, &x) && memcmp(m2, mac, 6) == 0 && node == 0 && x == 0x01);
    can_enum_assign_encode(mac, 5, 1, b);
    ASSERT_TRUE(can_enum_assign_decode(b, 8, m2, &node, &x) && node == 5 && x == 1 && memcmp(m2, mac, 6) == 0);
    uint8_t rq[2] = {3, 2}, rd, sm;
    ASSERT_TRUE(can_enum_req_decode(rq, 2, &rd, &sm) && rd == 3 && sm == 2);
}

TH_MAIN
