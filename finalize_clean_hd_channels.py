import os
import shutil
import sqlite3
import zipfile
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"c:\Users\oktce\Desktop\TVchannel"
RAW_ZIP = os.path.join(BASE_DIR, "Channel_list_T-KTM2DEUC-1400.2_DUAL_RAW_SCAN.zip")
WORK_DIR = os.path.join(BASE_DIR, "processed_final")
OUTPUT_LOCAL_ZIP = os.path.join(BASE_DIR, "Channel_list_T-KTM2DEUC-1400.2_DUZENLENMIS.zip")
USB_ZIP = r"E:\Channel_list_T-KTM2DEUC-1400.2.zip"

if os.path.exists(WORK_DIR):
    shutil.rmtree(WORK_DIR)
os.makedirs(WORK_DIR, exist_ok=True)

with zipfile.ZipFile(RAW_ZIP, 'r') as z:
    z.extractall(WORK_DIR)

db_path = os.path.join(WORK_DIR, "dvbs")
sat_path = os.path.join(WORK_DIR, "sat")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

conn_sat = sqlite3.connect(sat_path)
cur_sat = conn_sat.cursor()

def decode_name(val):
    if not val:
        return ""
    if isinstance(val, str):
        try:
            return val.encode('utf-16-be').decode('utf-16-le').strip('\x00')
        except Exception:
            return val
    return str(val)

def encode_name(text):
    return text.encode('utf-16-le').decode('utf-16-be')

# 1. KULLANICININ YASAKLADIĞI KANALLAR
USER_EXCLUDED = [
    "ULKE TV", "ÜLKE TV", "EKOL TV", "EKOTURK", "EKOTÜRK"
]

# 2. DİNİ KANALLAR VE RADYOLAR (TAMAMI KESİNTİSİZ ENGELLENDİ)
RELIGIOUS_KEYWORDS = [
    "DIYANET", "DİYANET", "SEMERKAND", "LALEGUL", "LALEGÜL", "HILAL", "HİLAL", 
    "KUDUS", "KUDÜS", "REHBER", "DOST TV", "DOST FM", "DOST RADYO", "CAGRI", "ÇAĞRI", 
    "AKIT", "AKİT", "BEDIR", "BEDİR", "VAV TV", "VAV RADYO", "VAV FM", "IKRA", 
    "ISLAM", "İSLAM", "ISLAMI", "KUR'AN", "KURAN", "QURAN", "SUNNAH", "MEKKE", 
    "MEDINE", "MEDİNE", "FM TV", "NUR TV", "MEHTAP", "AKRA FM", "MORAL FM", 
    "RADYO 7", "BURC FM", "HUZUR TV", "BEDIR TV", "SAT-7", "SAT7", "SAT 7",
    "PADRE PIO", "TELEPACE", "TV2000", "RADIO MARIA", "KTO", "SANCTUARY", "TBN", 
    "CHRISTIAN", "CHURCH", "EWTN", "SONLIFE", "DAYSTAR", "GOD TV", "PEACE TV", 
    "AHLULBAYT", "KARBALA", "IMAM HUSSEIN", "IQRAA", "MAKKAH", "MADINAH", "RIBAT FM",
    "ERKAM RADYO", "BAYRAM FM"
]

# 3. RUSÇA VE ÇÖP YAYINLAR
RUSSIAN_CHANNELS = [
    "RTR PLANETA", "RUSSIA 24", "NTV STYLE", "NTV PRAVO", "NTV SERIAL", "NTV MIR",
    "DOMASHNIY", "IZVESTIYA", "REN", "STS", "PERETS", "5 INTERNATIONAL", 
    "TNT INT", "TNT MUSIC", "UMKA", "START EPIC", "START AIR", "START WORLD", "MOSCOW 24"
]

# 4. REKLAM / ÇÖP / TEST / DUMMY KANALLARI
JUNK_KEYWORDS = [
    "TEK-1", "TEK-2", "TEK-3", "TEK-4", "SERVICE 1", "SERVICE 2", "SERVICE 3", "SERVICE 4",
    "PRD 1", "PRD 2", "PRD 3", "PRD 4", "PRD 6", "PRD 7", "INTERCOMM", "INTERCOM",
    "TURKSAT TANITIM", "PATI TV", "AYAZ TV", "0 SIFIR TV", "PERSIANA TURKIYE", "WITNESS EYE",
    "STOON TV", "DMAX SD", "TLC SD", "TOP SHOP", "SHOPPING", "TELEALISVERIS", "TELEALIŞVERİŞ",
    "BAL TV", "SAAT TV", "TEST", "TKGS", "SUSPEND", "OTA", "DOWNLOAD", "DATA", "ASFTV", "TEKNOFEST"
]

# 5. YETİŞKİN / ÇÖP SPAM
ADULT_KEYWORDS = [
    "XXX", "SEX", "ADULT", "CHAT", "BABE", "NIGHT", "EROTIC", "REDLIGHT", "PASSION"
]

def is_blacklisted(name):
    name_up = name.upper()
    for ex in USER_EXCLUDED:
        if ex in name_up:
            return True, f"Kullanıcı Engeli: {ex}"
    for rel in RELIGIOUS_KEYWORDS:
        if rel in name_up:
            return True, f"Dini İçerik: {rel}"
    for rus in RUSSIAN_CHANNELS:
        if rus in name_up:
            return True, f"Rusça: {rus}"
    for junk in JUNK_KEYWORDS:
        if junk in name_up:
            return True, f"Çöp/Test: {junk}"
    for ad in ADULT_KEYWORDS:
        if ad in name_up:
            return True, f"Yetişkin/Spam: {ad}"
    return False, ""

# 6. EKSİK TRANSPONDERLAR VE KANALLARIN TANIMLANMASI
# ATV HD (12207 H 27500), TV8 HD (11901 V 12500), BEYAZ TV HD (11996 V 27500)
NEW_TPS = [
    # tpId, satId, freq, pol, fec, sr
    (2920, 19, 12207000, 0, 3, 27500), # ATV TP
    (2921, 19, 11901000, 1, 2, 12500), # TV8 TP
    (2922, 19, 11996000, 1, 3, 27500)  # BEYAZ TV TP
]

for tp in NEW_TPS:
    tpId, satId, freq, pol, fec, sr = tp
    cur_sat.execute("SELECT COUNT(*) FROM SAT_TP WHERE tpId = ?", (tpId,))
    if cur_sat.fetchone()[0] == 0:
        cur_sat.execute("INSERT INTO SAT_TP VALUES (?, ?, ?, ?, ?, ?, 1, NULL)", (tpId, satId, freq, pol, fec, sr))
    
    chId = 0x00e00002 | (tpId << 6)
    cur.execute("SELECT COUNT(*) FROM CHNL WHERE chId = ?", (chId,))
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO CHNL VALUES (?, 7, ?, 2, ?, 3, 7, 65535, -1, ?, 1, 65535, NULL, '', NULL)", (chId, tpId, freq, pol))
        cur.execute("INSERT INTO SGNL VALUES (?, 100, 100, 0, NULL, NULL)", (chId,))

conn_sat.commit()
conn_sat.close()

# Enjekte Edilecek Yüksek Kalite HD Kanallar
INJECTED_CHANNELS = [
    # name, tpId, progNum, tsid, vidPid, srvType
    ("ATV HD", 2920, 10300, 103, 3050, 25),
    ("A HABER HD", 2920, 10301, 103, 3051, 25),
    ("A SPOR HD", 2920, 10302, 103, 3052, 25),
    ("MINIKA COCUK", 2920, 10306, 103, 3056, 25),
    ("MINIKA GO HD", 2920, 10307, 103, 3057, 25),
    ("TV8 HD", 2921, 15300, 153, 4300, 25),
    ("TV8.5 HD", 2921, 15301, 153, 4301, 25),
    ("BEYAZ TV HD", 2922, 51800, 518, 6800, 25)
]

for name, tpId, progNum, tsid, vidPid, srvType in INJECTED_CHANNELS:
    chId = 0x00e00002 | (tpId << 6)
    srvId = int(f"8109{tpId:04d}{progNum:05d}{vidPid % 1000:03d}")
    enc_name = encode_name(name)
    
    cur.execute("""
        INSERT OR REPLACE INTO SRV (
            srvId, chId, major, minor, progNum, srvName, srvType, tsid, vidEncType, 
            vidPid, pcr, lockMode, mem, memBySI, elim, hideGuide, hidden, srv3d, 
            scrambled, scrmInPMT, numSel, plpId, cacheId, resInfoType, resInfoWidth, 
            resInfoHeight, resInfoFrNum, resInfoFrDenom, htlProgType, modifiedByUser, 
            caDevId, caSrvType, caDevType, ipg, srcType, isAtscUHD, imclOrder, delSys, 
            defSrv, sync, recState
        ) VALUES (
            ?, ?, 999, 65534, ?, ?, ?, ?, 1, 
            ?, ?, 0, 1, 1, 0, 0, 0, 0, 
            0, 0, 1, 65535, 1, -1, 1920, 
            1080, -1, 0, -1, 0, 
            NULL, 0, -1, 0, 0, 0, 65535, -1, 
            NULL, NULL, NULL
        )
    """, (srvId, chId, progNum, enc_name, srvType, tsid, vidPid, vidPid))
    
    cur.execute("""
        INSERT OR REPLACE INTO SRV_DVB (
            srvId, nid, onid, lcn, hdLcn, hdSim, srvStat, provId, defAuthId, runSt, 
            eitPf, guid, mltLngSrvNameLang, mltLngSrvName, shrtSrvName, dataStream, 
            updByPsi, recState, carouselId
        ) VALUES (
            ?, 65535, 66, 65535, 65535, 0, 0, 1970334976745338, NULL, NULL, 
            1, NULL, 65535, NULL, NULL, NULL, 0, NULL, NULL
        )
    """, (srvId,))

# 7. TÜM KANALLARI OKU VE FİLTRELE
cur.execute("SELECT srvId, progNum, major, srvName, srvType, scrambled, vidPid, resInfoWidth, resInfoHeight FROM SRV")
rows = cur.fetchall()

to_delete = []
candidates_tv = []
candidates_radio = []

for r in rows:
    srvId, progNum, major, raw_name, srvType, scrambled, vidPid, w, h = r
    name = decode_name(raw_name).strip()
    
    # Şifreli kanallar
    if scrambled == 1:
        to_delete.append(srvId)
        continue
        
    # İsimsiz / Boş
    if not name or name.isspace():
        to_delete.append(srvId)
        continue
        
    is_radio = (srvType == 2)
    
    # TV ama yayını yoksa
    if not is_radio and vidPid == 65535:
        to_delete.append(srvId)
        continue
        
    # Kara liste kontrolü (Dini, çöp, kullanıcı isteği vb.)
    b_listed, reason = is_blacklisted(name)
    if b_listed:
        to_delete.append(srvId)
        continue
        
    obj = {
        'srvId': srvId,
        'progNum': progNum,
        'orig_major': major,
        'name': name,
        'raw_name': raw_name,
        'srvType': srvType,
        'vidPid': vidPid,
        'w': w,
        'h': h,
        'is_hd': (srvType == 25 or 'HD' in name.upper() or h >= 720)
    }
    
    if is_radio:
        candidates_radio.append(obj)
    else:
        candidates_tv.append(obj)

# 8. YÜKSEK KALİTE FİLTRESİ:
# Eğer bir TV kanalının hem HD hem de SD versiyonu varsa, SD olanı KESİNLİKLE SİL!
# (Kullanıcı: "hepsi yüksek kalite olsun")
sd_to_delete = []
for c in candidates_tv:
    if not c['is_hd']:
        # Aynı kanalın HD hali var mı?
        base_name = c['name'].upper().replace(" SD", "").replace(" TV", "").strip()
        has_hd = any(
            o['is_hd'] and base_name in o['name'].upper()
            for o in candidates_tv
        )
        if has_hd:
            sd_to_delete.append(c['srvId'])

for sid in sd_to_delete:
    to_delete.append(sid)

candidates_tv = [c for c in candidates_tv if c['srvId'] not in sd_to_delete]

# Çift TV kanallarını isim bazında ele (aynı isimden sadece 1 tane en iyi olanı kalsın)
seen_tv_names = set()
tv_kept = []
for c in candidates_tv:
    name_key = c['name'].upper().replace(" ", "").replace("TØÞK", "TURK").replace("TÜRK", "TURK")
    if name_key in seen_tv_names:
        to_delete.append(c['srvId'])
    else:
        seen_tv_names.add(name_key)
        tv_kept.append(c)

# Çift Radyoları isim bazında ele
seen_radio_names = set()
radio_kept = []
for r in candidates_radio:
    name_key = r['name'].upper().replace(" ", "").replace("TØÞK", "TURK").replace("TÜRK", "TURK").rstrip(".")
    if name_key in seen_radio_names:
        to_delete.append(r['srvId'])
    else:
        seen_radio_names.add(name_key)
        radio_kept.append(r)

# Veritabanından sil
for srvId in to_delete:
    cur.execute("DELETE FROM SRV_FAV WHERE srvId = ?", (srvId,))
    cur.execute("DELETE FROM SRV_DVB WHERE srvId = ?", (srvId,))
    cur.execute("DELETE FROM SRV WHERE srvId = ?", (srvId,))

# 9. KANAL SIRALAMASI
TV_PRIORITY = [
    # 1 - 9: Ulusal Ana Kanallar (Tamamı HD)
    "TRT1 HD", "ATV HD", "KANAL D HD", "SHOW HD", "STAR TV", "NOW HD", "TV8 HD", "KANAL 7 HD", "BEYAZ TV HD",
    
    # 10 - 15: Belgesel & Yaşam (Tamamı HD)
    "DMAX HD", "TLC HD", "TRT BELGESEL HD", "TV2 HD", "CNBC-E", "TGRT BELGESEL HD",
    
    # 16 - 18: TV Müzik (HD)
    "TRT MUZIK HD", "DREAM TØÞK", "NR1 TURK TV",
    
    # 19 - 28: Haber & Gündem (HD)
    "NTV", "TRT HABER HD", "CNN TØÞK HD", "HABER GLOBAL HD", "SZC", "HABERTURK HD", 
    "HALK TV", "A HABER HD", "TGRT HABER HD", "FLASH TV", "LİDER HABER HD",
    
    # 29 - 35: Spor Kanalları (HD)
    "BEIN SPORTS HABER", "TRT SPOR HD", "TRT SPOR YILDIZ", "A SPOR HD", "HT SPOR HD", "TV8.5 HD", "T.A.Y TV",
    
    # 36 - 40: Çocuk & Kültür (HD)
    "TRT COCUK HD", "MINIKA GO HD", "MINIKA COCUK", "CARTOON NETWORK", "TRT2 HD",
    
    # 41 - 50: Seçkin Kültür / Dünya / Kıbrıs (HD)
    "NHK WORLD-JPN", "TRT WORLD HD", "BLOOMBERGHT HD", "BRT 1 HD", "BRT 2 HD", 
    "KIBRIS TV HD", "EURO D HD", "EUROSTAR", "TV 2020", "ADA TV", "GENC TV"
]

def rank_tv(c):
    n = c['name'].upper()
    for idx, target in enumerate(TV_PRIORITY):
        if target == "NTV" and (n == "NTV" or n.startswith("NTV HD") or n.startswith("NTV SD")):
            return idx
        elif target != "NTV" and (target in n or n.startswith(target)):
            return idx
    # Geri kalanlar HD olanlar öne gelecek şekilde
    base = 1000 if c['is_hd'] else 2000
    return base + c['orig_major']

tv_kept.sort(key=rank_tv)

RADIO_PRIORITY = [
    "KRAL POP", "KRAL FM", "POWER FM", "POWERTURK FM", "METRO FM", "SUPER FM", "SÜPER FM",
    "SLOWTØÞK", "SLOW TURK", "JOYTURK FM", "JOY TURK", "JOY FM", "VIRGIN RADYO",
    "RADYO FENOMEN", "FENOMEN TURK", "BEST FM", "SHOW RADYO", "RADYO VİVA", "RADYO VIVA", 
    "RADYO D", "KAFA RADYO", "PAL NOSTALJI", "PAL STATION", "NR1 TURK FM", "NR1 FM",
    "RADYO SPOR", "TRT FM", "TRT RADYO HABER", "RADYO 1", "TRT NAGME", "TRT TURKU",
    "NTV RADYO", "CNN TØÞK RADYO", "45'LIK", "KALP FM", "POLIS RADYOSU", "TGRT FM", 
    "KARADENIZ FM", "RD SEYMEN"
]

def rank_radio(r):
    n = r['name'].upper()
    for idx, target in enumerate(RADIO_PRIORITY):
        if target in n or n.startswith(target):
            return idx
    return 500 + r['orig_major']

radio_kept.sort(key=rank_radio)

# 10. NUMARALANDIRMA
final_list = []

main_tv_channels = [c for c in tv_kept if rank_tv(c) < 1000]
other_tv_channels = [c for c in tv_kept if rank_tv(c) >= 1000]

# 1'den başla: Ana Seçkin HD TV Kanalları (1 - 52)
cur_num = 1
for c in main_tv_channels:
    cur.execute("UPDATE SRV SET major = ?, lockMode = 0, hideGuide = 0, hidden = 0, numSel = 1 WHERE srvId = ?", (cur_num, c['srvId']))
    c['new_major'] = cur_num
    final_list.append(c)
    cur_num += 1

# 61'den başla: Popüler Radyolar (Kesinlikle Dini Yok! 61 - 95)
cur_num = 61
for r in radio_kept:
    cur.execute("UPDATE SRV SET major = ?, lockMode = 0, hideGuide = 0, hidden = 0, numSel = 1 WHERE srvId = ?", (cur_num, r['srvId']))
    r['new_major'] = cur_num
    final_list.append(r)
    cur_num += 1

# 121'den başla: Diğer Temiz Açık TV Kanalları (121+)
cur_num = 121
for o in other_tv_channels:
    cur.execute("UPDATE SRV SET major = ?, lockMode = 0, hideGuide = 0, hidden = 0, numSel = 1 WHERE srvId = ?", (cur_num, o['srvId']))
    o['new_major'] = cur_num
    final_list.append(o)
    cur_num += 1

conn.commit()
cur.execute("PRAGMA integrity_check;")
print("Veritabanı Bütünlüğü:", cur.fetchone()[0])
cur.execute("VACUUM;")
conn.close()

# 11. PAKETLEME VE USB'YE YAZMA
with zipfile.ZipFile(OUTPUT_LOCAL_ZIP, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for fname in ["dvbs", "sat", "metadata.xml"]:
        fpath = os.path.join(WORK_DIR, fname)
        if os.path.exists(fpath):
            z.write(fpath, arcname=fname)

print(f"[✓] Yeni zip başarıyla oluşturuldu: {OUTPUT_LOCAL_ZIP}")

if os.path.exists(r"E:\ "):
    shutil.copy2(OUTPUT_LOCAL_ZIP, USB_ZIP)
    print(f"[✓] USB Belleğe kopyalandı: {USB_ZIP}")
elif os.path.exists("E:\\"):
    shutil.copy2(OUTPUT_LOCAL_ZIP, USB_ZIP)
    print(f"[✓] USB Belleğe kopyalandı: {USB_ZIP}")
else:
    print("[!] Uyarı: E:\\ sürücüsü bulunamadı.")

print("\n" + "=" * 60)
print("             SON YÜKSEK KALİTE (HD) KANAL DİZİLİMİ")
print("=" * 60)
for item in final_list:
    t = "RADYO" if item['srvType'] == 2 else "TV"
    if item['new_major'] <= 50 or (51 <= item['new_major'] <= 85):
        hd_label = "HD" if item.get('is_hd', False) else ""
        print(f"{item['new_major']:3d}. [{t:<5}] {item['name']:<25} {hd_label}")
