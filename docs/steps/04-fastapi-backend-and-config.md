# قدم ۴: سرور Backend با FastAPI در معماری شش‌ضلعی و ذخیره تنظیمات با Pydantic V2

## ۱. هدف این قدم

در این قدم وب‌سرور موقت پایتون (`http.server`) را کنار می‌گذاریم و **سرور اصلی Backend ایستگاه کنترل زمینی XeroxUAV** را با `FastAPI` و معماری شش‌ضلعی می‌سازیم؛ سروری که هم صفحه وب پخش زنده ما را سرو می‌کند و هم تنظیمات دوربین و آدرس‌ها را با اعتبارسنجی سخت‌گیرانه **Pydantic V2** در یک فایل استاندارد `TOML` روی دیسک ذخیره و بازیابی می‌کند.

**کجای نقشه بزرگ هستیم؟** در قدم ۳ صفحه وب سمت مرورگر ساخته شد. امروز مغز مرکزی روی لپ‌تاپ (`FastAPI Backend`) آماده می‌شود تا در قدم ۵ سرویس **Pi-Agent** روی رزبری‌پای با `WebSocket` به همین سرور وصل شود و در قدم ۶ دکمه‌های تغییر زنده رزولوشن در مرورگر از طریق همین سرور به رزبری‌پای فرمان بدهند!

---

## ۲. مفاهیم جدید (از صفر مطلق)

قبل از دیدن کد، ۵ مفهوم کلیدی دنیای Backend را ساده و دقیق یاد بگیریم:

### ۱. نقش `Backend`، زبان `JSON` و الگوی `REST API`
تصور کن یک رستوران مدرن داریم:
- صفحه وب در مرورگر (`Frontend`) مثل **میز مشتری و منوی لمسی** است.
- سرور **Backend** مثل **سرآشپز و دفتر ثبت سفارش** در آشپزخانه است.
- مرورگر و سرور با قالب متنی سبکی به نام **`JSON`** با هم صحبت می‌کنند که دقیقاً شبیه دیکشنری است؛ مثلاً:
  `{"resolution": "960x600", "fps_hz": 30, "bitrate_kbps": 2000, "encoder_kind": "software_x264"}`.
- الگوی **`REST API`** می‌گوید به جای ساختن دستورهای پراکنده، هر منبع یک آدرس مشخص (مثل `/api/v1/config/stream`) داشته باشد و با فعل‌های استاندارد HTTP با آن کار کنیم:
  - **`GET`:** فقط خواندن تنظیمات فعلی (بدون هیچ تغییری).
  - **`PUT`:** جایگزین کردن تنظیمات استریم با مقادیر جدید و ذخیره روی دیسک.
  - **`POST`:** اجرای یک عملیات خاص (مثل `/api/v1/config/stream/reset` برای بازگشت به پیش‌فرض).
- **کدهای وضعیت پاسخ:** کد **`200`** یعنی «همه‌چیز موفق بود»، کد **`422`** (`Unprocessable Content`) یعنی «JSON را خواندم اما مقادیرت غیرمجاز است؛ مثلاً رزولوشن `1280x720` یا ترکیب غیرمجاز `1920x1200 + hardware_v4l2` فرستادی!» و کد **`500`** یعنی خطای داخلی مثل مشکل نوشتن روی دیسک.

### ۲. تفاوت `FastAPI`، استاندارد `ASGI` و سرور `Uvicorn`
چرا در پایتون هم اسم **`FastAPI`** را می‌بینیم و هم **`Uvicorn`**؟
- **`Uvicorn`** مثل اپراتور مخابرات است: پورت شبکه (`8080`) را باز می‌کند، بسته‌های HTTP را به‌صورت ناهمگام (`async`) دریافت می‌کند و پاسخ‌ها را روی سیم برمی‌گرداند.
- **`FastAPI`** مغز برنامه‌نویسی ماست: مشخص می‌کند هر آدرس وب به کدام تابع پایتون برود و خروجی را خودکار به JSON تبدیل می‌کند.
- استاندارد ارتباط بین `Uvicorn` و `FastAPI` را **`ASGI`** (مخفف *Asynchronous Server Gateway Interface*) می‌نامند.
- همچنین با قابلیت `StaticFiles` در FastAPI، پوشه صفحه وب قدم ۳ را روی آدرس ریشه `/` سوار کردیم؛ یعنی با اجرای همین یک دستور، هم API و هم صفحه وب پخش زنده با هم بالا می‌آیند! *(نکته آفلاین: صفحه پیش‌فرض `/docs` در FastAPI فایل‌هایش را از اینترنت دانلود می‌کند؛ چون شبکه پرواز تیم اینترنت ندارد، آن را غیرفعال کردیم و نقشه آفلاین API را در `/api/openapi.json` نگه داشتیم.)*

### ۳. گیت بازرسی `Pydantic V2` در مرز برنامه در برابر `dataclass` در هسته
یک قانون طلایی مهندسی نرم‌افزار در تیم ما این است:
- **در مرزهای بیرونی برنامه** (خواندن فایل از دیسک یا گرفتن JSON از مرورگر) به هیچ داده‌ای اعتماد نکن! اینجا از **`Pydantic V2` (`BaseModel`)** استفاده می‌کنیم که مثل مأمور سخت‌گیر گیت فرودگاه، نوع داده‌ها، بازه اعداد (`5 <= fps_hz <= 60`) و حتی غلط‌های املایی نام فیلدها (`extra="forbid"`) را بررسی می‌کند.
- **در هسته داخلی برنامه (`domain`)** پس از عبور از گیت بازرسی، داده‌ها را به اشیاء سریع و تغییرناپذیر **`@dataclass(frozen=True, slots=True)`** تبدیل می‌کنیم تا هسته منطق ما هیچ وابستگی‌ای به فریم‌ورک‌های وب نداشته باشد.

### ۴. فایل تنظیمات `TOML` و ترفند «نوشتن اتمی» (`Atomic Write`)
- **`TOML`** همان فرمت تمیز و دسته‌بندی‌شده‌ای است که در `pyproject.toml` دیده‌ای (`[server]`، `[mediamtx]`، `[stream]`). برای خواندن آن از ماژول استاندارد خود پایتون (`tomllib`) و برای نوشتنش از کتابخانه سبک `tomli_w` استفاده می‌کنیم.
- **نوشتن اتمی چیست؟** اگر برنامه مستقیم روی فایل `configs/backend.toml` بنویسد و وسط کار برق لپ‌تاپ برود، فایل نیمه‌کاره و خراب می‌شود! ما اول کل تنظیمات جدید را در فایل موقت `backend.toml.tmp` می‌نویسیم و سپس در یک دستور اتمی سیستم‌عامل (`temp_path.replace`) آن را جایگزین فایل اصلی می‌کنیم تا فایل تنظیمات **هرگز** نیمه‌کاره نماند.

### ۵. جهت فلش‌ها در معماری شش‌ضلعی (`Hexagonal Architecture`)

```text
  [مرورگر وب / CLI]                 [فایل configs/backend.toml]
         │                                       ▲
         ▼ (presentation/backend)                │ (infrastructure/persistence)
   FastAPI Routes + DTOs                TomlConfigRepository + Pydantic
         │                                       │
         └──────────────► ConfigService ─────────┘
                          (application)
                                │
                                ▼
                  BackendRuntimeConfig / StreamConfig
                     + ConfigRepositoryPort
                         (domain خالص)
```

دقت کن: لایه `domain` و `application` روحشان هم خبر ندارد که بیرون از آن‌ها `FastAPI` است یا فایل `TOML`! به همین دلیل در تست‌ها می‌توانیم بدون باز کردن حتی یک پورت واقعی یا فایل واقعی، کل منطق را در چند میلی‌ثانیه تست کنیم.

---

## ۳. کارهایی که انجام شد (فایل‌به‌فایل)

| مسیر فایل | دلیل وجود فایل |
| :--- | :--- |
| `pyproject.toml` و `uv.lock` | افزودن وابستگی‌های `fastapi`، `uvicorn`، `tomli-w` (و `httpx2` برای تست) و ثبت دستور CLI جدید `xerox-cam-backend`. |
| `configs/backend.example.toml` | نمونه مستندشده فایل تنظیمات سرور (خودِ فایل `configs/backend.toml` در اولین اجرا خودکار ساخته می‌شود و در `.gitignore` است تا IP محلی کامیت نشود). |
| `src/real_time_cam/domain/{constants,errors,entities,ports}.py` | افزودن اشیاء دامنه `BackendServerSettings`، `MediaMtxSettings`، `BackendRuntimeConfig`، بررسی سازگاری سخت‌افزار رزبری‌پای ۴ (`validate_pi4_live_compatibility`) و پورت انتزاعی `ConfigRepositoryPort`. |
| `src/real_time_cam/application/config_service.py` | سرویس کاربردی `ConfigService` با رعایت جداسازی پرس‌وجو و فرمان (`get_stream_config` در برابر `apply_stream_config`). |
| `src/real_time_cam/infrastructure/persistence/config_models.py` | مدل‌های مرزی **Pydantic V2** برای بخش‌های `[server]`، `[mediamtx]` و `[stream]` با `extra="forbid"`. |
| `src/real_time_cam/infrastructure/persistence/toml_config_repository.py` | پیاده‌سازی `TomlConfigRepository` با ایجاد خودکار فایل پیش‌فرض و نوشتن اتمی روی دیسک. |
| `src/real_time_cam/presentation/backend/{schemas,routes,app_factory,cli}.py` | مسیرهای REST API (`/api/v1/health`, `/api/v1/config`, `/api/v1/config/stream`)، سرو فایل‌های استاتیک وب روی `/` و راه‌انداز خط فرمان `xerox-cam-backend`. |
| `src/real_time_cam/presentation/web/js/{api-client,constants,whep-client,app}.js` | اتصال خودکار صفحه وب به `/api/v1/config` در لحظه باز شدن تا پورت و مسیر WHEP از تنظیمات سرور خوانده شود. |
| `tests/{application,infrastructure,presentation}/...` | مجموعه کامل تست‌های واحد و یکپارچه‌سازی (ارتقا از ۵۶ به **۷۶ تست سبز** با پوشش شاخه‌ای **`97.83%`**). |

---

## ۴. کد با توضیح خط‌به‌خط

### الف) محافظت از محدودیت سخت‌افزاری رزبری‌پای ۴ در لایه `domain` (`domain/entities.py`)

یادمان هست در بنچمارک واقعی قدم ۲ کشف کردیم چیپ سخت‌افزاری `hardware_v4l2` روی رزبری‌پای ۴ سقف ارتفاع `1080` پیکسل دارد و روی `1920x1200` خطا می‌دهد؟ حالا این دانش واقعی سخت‌افزار را مستقیم وارد قوانین دامنه کردیم:

```python
def validate_pi4_live_compatibility(self) -> None:
    is_v4l2 = self.encoder_kind == EncoderKind.HARDWARE_V4L2
    if is_v4l2 and self.resolution.height_px > PI4_H264_LEVEL_4_MAX_HEIGHT_PX:
        msg = (
            f"hardware_v4l2 on Raspberry Pi 4 supports heights up to "
            f"{PI4_H264_LEVEL_4_MAX_HEIGHT_PX} px; use software_x264 for "
            f"{self.resolution.get_label()}."
        )
        raise InvalidStreamConfigError(msg)
```
به لطف این متد، نه در فایل `backend.toml` و نه از طریق درخواست HTTP، هیچ‌کس نمی‌تواند به اشتباه ترکیب خراب `1920x1200 + hardware_v4l2` را ذخیره کند!

---

### ب) گیت اعتبارسنجی Pydantic V2 و نوشتن اتمی TOML (`infrastructure/persistence/`)

در `config_models.py`، ویژگی `ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)` روی تمام مدل‌ها تنظیم شده است:
- `str_strip_whitespace=True`: فاصله‌های اضافی اول و آخر رشته‌ها را خودکار پاک می‌کند.
- `extra="forbid"`: اگر کسی در فایل `backend.toml` به اشتباه بنویسد `bit_rate = 2000` (به جای `bitrate_kbps = 2000`)، به جای نادیده گرفتن بی‌صدا، فوراً خطای دقیق می‌دهد!

و در `toml_config_repository.py` نوشتن اتمی به این شکل انجام می‌شود:

```python
schema = BackendConfigFileSchema.from_domain(config)
toml_text = tomli_w.dumps(schema.model_dump(mode="json"))
temp_path = self._config_path.with_suffix(".toml.tmp")
self._config_path.parent.mkdir(parents=True, exist_ok=True)
temp_path.write_text(toml_text, encoding="utf-8")
temp_path.replace(self._config_path)
```
اول فایل موقت `.toml.tmp` کامل نوشته می‌شود و بعد در یک حرکت اتمی جای `backend.toml` می‌نشیند.

---

### ج) سرویس کاربردی با جداسازی پرس‌وجو و فرمان (`application/config_service.py`)

```python
def apply_stream_config(self, new_stream: StreamConfig) -> None:
    new_stream.validate_pi4_live_compatibility()
    updated_config = replace(self._config, stream=new_stream)
    self._repository.save(updated_config)
    self._config = updated_config
```
دقت کن ترتیب خط‌ها چقدر مهم است: اول روی دیسک ذخیره می‌کنیم (`self._repository.save`) و **فقط اگر ذخیره دیسک موفق بود** متغیر حافظه `self._config` را عوض می‌کنیم تا حافظه و دیسک هرگز با هم ناهماهنگ نشوند!

---

### د) سوار کردن هم‌زمان API و صفحه وب در FastAPI (`presentation/backend/app_factory.py`)

```python
app.include_router(build_api_router(config_service))
app.mount("/", StaticFiles(directory=web_root, html=True), name="web-ui")
```
چون اول `include_router` صدا زده شده، تمام آدرس‌های `/api/v1/...` به توابع پایتون می‌روند و بقیه آدرس‌ها (مثل `/` و `/js/app.js`) فایل‌های صفحه وب ما را برمی‌گردانند.

---

## ۵. چه کاری باید بکنی

*(مثل قدم ۳، روی رزبری‌پای نیازی به تغییر هیچ فایلی نیست؛ تمام کارهای این قدم روی لپ‌تاپ انجام می‌شود.)*

### مرحله ۱: همگام‌سازی وابستگی‌ها و اجرای تست‌ها در لپ‌تاپ
فایل‌های جدید را در `C:\Users\parsa\Documents\configurator` قرار بده و در **PowerShell لپ‌تاپ** دستورات زیر را بزن:

```powershell
cd C:\Users\parsa\Documents\configurator
uv sync --locked --dev
uv run ruff check .
uv run ty check
uv run pytest
```
**خروجی مورد انتظار:** نصب سریع `fastapi` و `uvicorn` و پاس شدن تمام **۷۶ تست (`76 passed`)**.

---

### مرحله ۲: تست ساخت خودکار فایل `configs/backend.toml`
حالا دستور بررسی کانفیگ را در PowerShell لپ‌تاپ اجرا کن:

```powershell
uv run xerox-cam-backend --check-config
```
**خروجی مورد انتظار:**
```text
Config OK (configs\backend.toml): bind=0.0.0.0:8080, whep=/cam/whep, stream=960x600@30Hz
```
اگر الان فایل `configs\backend.toml` را باز کنی، می‌بینی که با مقادیر پیش‌فرض استاندارد ساخته شده است!

---

### مرحله ۳: اجرای سرور اصلی FastAPI و تماشای تصویر زنده!
*(اگر پنجره `python -m http.server` قدم ۳ هنوز باز است، آن را با `Ctrl+C` ببند تا پورت `8080` آزاد باشد.)*
مطمئن شو `mediamtx.exe` روی لپ‌تاپ و ارسال تصویر رزبری‌پای روشن‌اند، سپس سرور اصلی را روشن کن:

```powershell
uv run xerox-cam-backend
```
**خروجی مورد انتظار:**
`Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)`

حالا در مرورگر به **`http://127.0.0.1:8080`** برو:
1. صفحه وب مستقیم از سرور FastAPI بارگذاری می‌شود، تنظیمات را از `/api/v1/config` می‌گیرد و تصویر زنده دوربین پخش می‌شود!
2. در یک پنجره PowerShell دیگر روی لپ‌تاپ، خواندن و تغییر ذخیره تنظیمات را با دستور زیر امتحان کن:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/api/v1/config/stream
```
و برای تست ذخیره تنظیمات جدید روی دیسک:
```powershell
Invoke-RestMethod -Method Put -Uri http://127.0.0.1:8080/api/v1/config/stream `
  -ContentType "application/json" `
  -Body '{"resolution":"1920x1200","fps_hz":25,"bitrate_kbps":3000,"encoder_kind":"software_x264"}'
```
حالا محتوای `configs\backend.toml` را نگاه کن؛ می‌بینی که مقادیر جدید روی دیسک ذخیره شده‌اند! (برای برگرداندن به حالت پیش‌فرض کافی است بزنی: `Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/v1/config/stream/reset`).

---

## ۶. اگر خطا دیدی

۱. **خطای `[Errno 10048] error while attempting to bind on address ('0.0.0.0', 8080)` هنگام اجرای `uv run xerox-cam-backend`:**
- **معنی:** پورت `8080` توسط برنامه دیگری (احتمالاً همان `python -m http.server` قدم قبل!) اشغال است.
- **راه‌حل:** پنجره قبلی را با `Ctrl+C` ببند، یا موقتاً با `--port 8090` سرور را روی پورت دیگری بالا بیاور.

۲. **خطای `Configuration error: Invalid configuration in 'configs\backend.toml'`:**
- **معنی:** فایل `configs\backend.toml` به صورت دستی ویرایش شده و یک نام فیلد اشتباه یا مقدار خارج از محدوده داخلش قرار گرفته است.
- **راه‌حل:** متن دقیق خطا نام فیلد مشکل‌دار را نشان می‌دهد؛ آن را اصلاح کن یا فایل `configs\backend.toml` را پاک کن تا دوباره نسخه پیش‌فرض سالم ساخته شود.

۳. **دریافت خطای `422` هنگام ارسال درخواست `PUT`:**
- **معنی:** گیت اعتبارسنجی Pydantic V2 جلوی داده نامعتبر (مثلاً رزولوشن غیرمجاز یا ترکیب `1920x1200` با `hardware_v4l2`) را گرفته است.

---

## ۷. خودت را بسنج

۱. **آزمایش گیت Pydantic V2:** در PowerShell تلاش کن با دستور `Invoke-RestMethod -Method Put` ترکیب `1920x1200` و `"hardware_v4l2"` را به `/api/v1/config/stream` بفرستی. سرور چه کد وضعیتی برمی‌گرداند؟
۲. **پایداری بعد از ری‌استارت:** با یک درخواست `PUT` نرخ بیت را روی `2500` بگذار، سرور `xerox-cam-backend` را با `Ctrl+C` خاموش و دوباره روشن کن و `GET /api/v1/config/stream` بزن. آیا عدد `2500` حفظ شده است؟ چرا؟
۳. **سؤال معماری:** چرا کلاس `ConfigService` در لایه `application` مستقیم `tomllib` را `import` نکرده و به جای آن از `ConfigRepositoryPort` استفاده کرده است؟

---

## ۸. چه چیزی یاد گرفتیم + قدم بعدی

**خلاصه این قدم:**
سرور اصلی Backend را با **FastAPI** و **Uvicorn** در معماری شش‌ضلعی ساختیم، مرزهای ورودی HTTP و فایل تنظیمات `TOML` را با **Pydantic V2** ایمن کردیم، نوشتن اتمی روی دیسک را پیاده کردیم و صفحه وب پخش زنده را به سرور متصل نمودیم.

**در قدم ۵ چه می‌کنیم؟**
می‌رویم سراغ قلب تپنده سمت پرنده: **سرویس پایتونی `Pi-Agent` روی رزبری‌پای**! یاد می‌گیریم پروتکل دوطرفه **`WebSocket`** چیست و چطور `Pi-Agent` پایپ‌لاین GStreamer را به صورت خودکار نظارت (Supervise)، راه‌اندازی، ری‌استارت و در صورت کرش با الگوریتم **Exponential Backoff** بازیابی می‌کند و به سرور FastAPI ما وصل می‌شود!
