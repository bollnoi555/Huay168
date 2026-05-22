# Telegram Lotto Bot

ระบบบอต Telegram สำหรับดูผลหวยลาวพัฒนาและหวยไทยย้อนหลัง 2 งวดล่าสุด พร้อมคำสั่งวิเคราะห์เชิงสถิติพื้นฐานและแจ้งเตือนเมื่อพบงวดใหม่

> หมายเหตุ: การวิเคราะห์เป็นสถิติจากผลย้อนหลัง ไม่ใช่การทำนายที่การันตีผล หวยเป็นเหตุการณ์สุ่ม ควรใช้เพื่อดูแนวโน้มเท่านั้น

## คำสั่งใน Telegram

- `/start` แสดงเมนูคำสั่ง
- `/thai` ดูผลหวยไทย 2 งวดล่าสุด
- `/lao` ดูผลหวยลาวพัฒนา 2 งวดล่าสุด
- `/latest` ดูทั้งหวยไทยและหวยลาว
- `/analyze_thai` วิเคราะห์หวยไทยจากข้อมูลย้อนหลังที่ดึงได้
- `/analyze_lao` วิเคราะห์หวยลาวจากข้อมูลย้อนหลังที่ดึงได้
- `/analyze` วิเคราะห์ทั้งสองชุด
- `/notify_on` สมัครรับแจ้งเตือนในแชทปัจจุบัน
- `/notify_off` ยกเลิกแจ้งเตือนในแชทปัจจุบัน
- `/chatid` ดู chat id สำหรับตั้งค่าแชท/กลุ่ม

## วิธีใช้งาน

1. สร้างบอตจาก BotFather แล้วคัดลอก token
2. คัดลอก `.env.example` เป็น `.env`
3. ใส่ค่า `TELEGRAM_BOT_TOKEN`
4. ถ้าต้องการผลหวยลาว ให้ใส่ `LAO_API_KEY`
5. รัน:

```powershell
python bot.py
```

ทดสอบดึงข้อมูลครั้งเดียวโดยไม่เปิดบอต:

```powershell
python bot.py --once
```

ถ้า API ภายนอกใช้ไม่ได้ ให้คัดลอก `manual_results.example.json` เป็น `data/manual_results.json` แล้วใส่ผลหวยเอง บอตจะใช้ไฟล์นี้ก่อน API เสมอ เหมาะสำหรับทดสอบหรือใช้เป็นแหล่งข้อมูลสำรอง

## รันบน GitHub Actions

GitHub Actions ไม่ใช่เซิร์ฟเวอร์ 24/7 แท้ ๆ เพราะ job มีเวลาจำกัด บอตนี้จึงตั้ง workflow ให้รันเป็นรอบ ๆ และเริ่มใหม่ทุก 6 ชั่วโมง

ตั้งค่า Secrets ที่ GitHub:

1. ไปที่ `Settings > Secrets and variables > Actions > New repository secret`
2. เพิ่ม `TELEGRAM_BOT_TOKEN` แล้วใส่ token จาก BotFather
3. ถ้าต้องการแจ้งเตือนแชทตั้งแต่เริ่ม ให้เพิ่ม `TELEGRAM_DEFAULT_CHAT_IDS`
4. ถ้ามีคีย์หวยลาว ให้เพิ่ม `LAO_API_KEY`
5. ไปที่ `Actions > Telegram Lotto Bot > Run workflow`

อย่าอัปโหลดไฟล์ `.env` ขึ้น GitHub

## แหล่งข้อมูลที่ตั้งไว้

- หวยลาวพัฒนา: `https://api.apilotto.com/api/v1/laolottohistory` ใช้ header `x-api-key`
- หวยไทย: `https://lotto.api.rayriffy.com` รองรับ `/list/:page` และ `/lotto/:id`

ถ้า endpoint เปลี่ยน ให้แก้ค่าใน `.env` โดยไม่ต้องแก้โค้ด
