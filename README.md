# DevCpp-AI (Bloodshed Dev-C++ 5.11)

ไฟล์เดียว `DevCpp-AI.exe` รวม Bloodshed Dev-C++ 5.11 + AI Chat

## สิ่งที่ได้

- ดับเบิลคลิกแล้วแตกติดตั้งไปที่ `%LOCALAPPDATA%\DevCpp-AI\` อัตโนมัติ
- เปิด Dev-C++ 5.11 พร้อมหน้าต่าง **AI Chat**
- เชื่อม [Dify API](https://api.dify.ai/v1) เป็นค่า default (`ai_config.json`)
- Hotspot default: SSID `hah` (รหัสใน `secrets.local.json`) — พยายามต่อเมื่อมี
- ถ้าไม่มี Hotspot ใช้ **LAN ได้** (`allow_lan_fallback`)
- แสดงข้อความ AI แบบเน้น (`**ตัวหนา**`) และรองรับพิมพ์ไทย
- **อย่า commit** `secrets.local.json` — ใช้ `secrets.local.example.json` เป็นตัวอย่าง
- ปุ่ม **Uninstall** ลบเฉพาะไฟล์ของ DevCpp-AI (ไม่แตะ Bloodshed เดิมใน Program Files)

## สร้างไฟล์ exe

```powershell
cd d:\Project\DevC+++
python tools\pack_payload.py
python tools\build_exe.py
```

ได้ไฟล์ที่ `dist\DevCpp-AI.exe`

## แจกผ่าน Personal Hotspot / เว็บ local

```powershell
python tools\share_server.py --port 8080
```

เปิด URL ที่พิมพ์บนจอจากเครื่องอื่นที่ต่อฮอตสปอตเดียวกัน แล้วกดดาวน์โหลด

หรือส่ง `DevCpp-AI.exe` ตรงๆ จากมือถือก็ได้

## รันแบบพัฒนา (ไม่แพ็ก)

```powershell
$env:PYTHONPATH="d:\Project\DevC+++\src"
python -m devcpp_ai
```

ต้องมี `payload\Dev-Cpp\devcpp.exe` (คัดลอกจาก Bloodshed ที่ติดตั้งไว้)

## ซอร์ส Delphi

อยู่ที่ `source\orwelldevcpp` (Orwell/Bloodshed 5.11)  
ดู `source\patches\README_AI_CHAT.md` หากจะ merge แท็บ Chat เข้า IDE ด้วย Delphi
