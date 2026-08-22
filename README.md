# GifBox

[![build](https://github.com/XamTE/gifbox/actions/workflows/build.yml/badge.svg)](https://github.com/XamTE/gifbox/actions/workflows/build.yml)

webp · mp4 등을 GIF로 바꾸고, 결과를 바로 클립보드에 올려주는 도구.
디스코드에 GIF 올리는 워크플로를 겨냥해 만들었습니다.

> **받으러 가기 → [최신 릴리스](https://github.com/XamTE/gifbox/releases/latest)**
> `GifBox-full.exe` 하나만 받으면 됩니다. 설치도, 파이썬도 필요 없습니다.

## 실행

| 파일 | 용도 |
|---|---|
| `dist\GifBox.exe` | **빌드한 실행 파일.** 파이썬 없이 이것만 있으면 됩니다 |
| `GifBox.bat` | 소스에서 창 띄우기 (개발 중에 사용) |
| `GIF변환.bat` | 파일을 끌어다 놓으면 콘솔에서 바로 변환 |
| `to_gif.py` | 명령줄 버전 |

본 창에는 **이번에 어떻게 변환할지**(프리셋·크기·자르기·목표 용량)만 두고,
한 번 정해두면 잘 안 바꾸는 것들(클립보드·원본 삭제·항상 위 …)은 오른쪽 위
**⚙ 설정** 창으로 모았습니다.

창을 띄워두고 파일을 끌어다 놓으면 변환되고, 결과 GIF가 클립보드에 올라갑니다.
그대로 **Ctrl+V** 로 카카오톡·디스코드·슬랙·탐색기 어디든 붙여넣으면 됩니다.
반대로 탐색기에서 파일을 Ctrl+C 한 뒤 창에서 **Ctrl+V** 를 눌러도 변환됩니다.

### exe 빌드

```bash
python build_exe.py
```

| 명령 | 결과 | 비고 |
|---|---|---|
| `python build_exe.py` | 18MB 한 파일 | ffmpeg는 PC에 설치된 걸 씀 |
| `python build_exe.py --with-ffmpeg` | 100MB 한 파일 | 아무것도 없는 PC에서도 동작 |
| `python build_exe.py --onedir` | 폴더 형태 | 시작이 빠름 |
| `python build_exe.py --cli` | `to_gif.exe` 도 함께 | 콘솔 버전 |

ffmpeg를 안 넣어도 exe는 실행할 때 `PATH → exe 옆 → 번들 안 → winget 경로 →
imageio-ffmpeg` 순으로 찾습니다. 그래서 `ffmpeg.exe` 를 `GifBox.exe` 옆에 복사해두는
것만으로도 동작합니다(다시 빌드할 필요 없음).

아이콘은 `make_icon.py` 가 만듭니다. 바꾸고 싶으면 그 파일을 고치고 다시 실행하세요.

### 배포 (GitHub Releases)

`v` 로 시작하는 태그를 밀면 GitHub Actions 가 Windows 러너에서 빌드해
릴리스에 exe 두 개를 붙입니다.

```bash
git tag v1.0.0 && git push origin v1.0.0
```

| 파일 | 설명 |
|---|---|
| `GifBox-full.exe` | ffmpeg 포함. 받는 사람은 이것만 받으면 됩니다 |
| `GifBox.exe` | 가벼운 쪽. ffmpeg 가 이미 있는 PC용 |

빌드 뒤 러너에서 `--selftest` 를 돌려 **tkdnd·ImageTk·ffmpeg 가 번들에서 빠지지
않았는지** 확인하고, 하나라도 실패하면 빌드를 실패시킵니다. 이것들은 빠져도 exe 는
멀쩡히 만들어지고 실행할 때가 되어서야 조용히 기능만 죽기 때문입니다.

**받는 사람에게 미리 알려줄 것:** 코드 서명 인증서를 붙이지 않아서 처음 실행할 때
Windows SmartScreen 이 파란 경고창을 띄웁니다. **추가 정보 → 실행** 을 누르면 됩니다.
백신 오탐도 가끔 있는데 PyInstaller 로 묶은 exe 에서 흔한 일입니다.

### 문제가 생기면

```bash
dist\GifBox.exe --selftest report.json
```

ffmpeg를 찾았는지, 드래그앤드롭(tkdnd)이 살아있는지, 클립보드가 되는지를
JSON으로 적어줍니다. 창 버전은 콘솔이 없어서 파일 경로를 인자로 받습니다.

### 프리셋

| 프리셋 | 설정 |
|---|---|
| 🎮 디스코드용 | 10MB 이하 · 가로 480 · 15fps |
| 😀 디스코드 이모지 | 256KB 이하 · 128×128 |
| ⚡ 초경량 | 2MB 이하 · 가로 320 · 10fps |
| 💎 고화질 | 용량 제한 없음 · 원본 크기 · 24fps |

창 맨 위에서 고르면 나머지 옵션이 한 번에 바뀝니다. CLI는 `--preset discord`,
목록은 `--presets`.

### 구간 자르기 · 목표 용량

웃긴 부분은 보통 몇 초뿐인데 영상 전체를 변환하면 용량만 커집니다.
`자르기 시작`·`길이`에 `0:12` / `4` 처럼 넣으면 그 구간만 변환합니다.

`목표 MB`를 넘으면 **가로크기 → fps → 색상수** 순으로 낮춰가며 자동으로 다시
변환합니다(최대 4회). 화질에 영향이 적은 것부터 손대는 순서입니다.
결과가 목표를 못 맞추면 로그에 그렇게 표시하고, 만든 것 중 가장 작은 걸 남깁니다.

```bash
python to_gif.py clip.mp4 --preset discord --trim 0:12-0:16
```

### 최근 기록 (썸네일 격자)

만든 GIF는 창의 **최근** 탭에 썸네일 격자로 쌓입니다. 이름만 봐서는 어떤 GIF인지
떠올리기 어려우니 그림으로 고르게 했습니다.

- **마우스를 올리면 움직입니다** — 정지 프레임만으로는 구분이 안 되는 경우가 많아서
- **더블클릭하면 다시 변환하지 않고 바로 클립보드로** — 같은 리액션 GIF를 반복해서 올릴 때
- 썸네일 아래 `📁` 로컬 / `🌐` 웹에서 가져온 것 / `⚠` 파일이 사라진 것

첫 프레임은 `%APPDATA%\GifBox	humbs` 에 캐시합니다. 캐시 키에 파일의 수정시각과
크기가 들어가므로 같은 이름으로 내용이 바뀌면 알아서 다시 굽습니다.
움직이는 프레임은 캐시하지 않고 마우스를 올린 순간에만 읽어 두었다가 벗어나면 놓아줍니다
(프레임을 전부 들고 있으면 메모리를 많이 먹습니다).

### 웹에서 가져오기

인터넷 이미지도 넣는 방법이 세 가지 있습니다.

1. **브라우저에서 이미지를 창으로 그대로 드래그** — 이때 창에 떨어지는 건 파일이
   아니라 이미지 '주소'입니다. GifBox가 그걸 받아 내려받은 뒤 변환합니다.
2. **이미지 우클릭 → '이미지 주소 복사' → 창에서 Ctrl+V**
3. **창 아래 주소 칸에 붙여넣고 Enter** (드래그가 안 먹는 사이트용)

결과는 `내려받기\GifBox` 에 저장되고(설정의 `web_outdir` 로 변경), 내려받은 원본은
임시 파일이라 자동으로 지워집니다. 이미 GIF인 이미지는 다시 인코딩해서 망치지 않고
그대로 저장합니다 — 용량을 줄이려면 창에서 'GIF 다시 인코딩'을 켜세요.

```bash
python to_gif.py 파일.mp4 --fps 15 --width 480
```

```bash
python to_gif.py https://example.com/anim.webp --width 480
```

주요 옵션: `--keep`(원본 유지) `--purge`(영구 삭제) `--copy`/`--no-copy`(클립보드)
`--dry-run` `-o`(출력 폴더) `-r`(하위 폴더) `--colors` `--all-types` `--overwrite`
`--reencode-gif` `--web-outdir`

## 구조

```
gifbox/
  theme.py       디스코드풍 어두운 팔레트 + ttk 스타일 (색은 전부 여기)
  settings.py    설정값 정의 + JSON 저장 (%APPDATA%\GifBox\settings.json)
  settings_dialog.py  ⚙ 설정 창 (켜고 끄는 항목은 전부 여기로)
  presets.py     프리셋 레지스트리 (디스코드용 / 이모지 / 초경량 / 고화질)
  history.py     최근 만든 GIF 목록 (history.json)
  thumbs.py      썸네일 굽기·캐시 + 호버 재생용 프레임 읽기
  sources.py     입력 소스 레지스트리 (로컬 파일 / 웹 주소 다운로드)
  converters.py  입력 포맷별 변환 엔진 레지스트리 (그대로저장 / ffmpeg / Pillow)
  actions.py     변환 후 동작 레지스트리 (클립보드 복사 / 원본 삭제 / 폴더 열기)
  pipeline.py    소스 해석 → 수집 → 변환 → 후처리 흐름 + Options/Result
  clipboard.py   Windows 클립보드 (파일 복사·이미지 복사·붙여넣기)
  winutil.py     휴지통, 탐색기 열기
  gui.py         창 (tkinter)
to_gif.py        명령줄 진입점
GifBox.pyw       창 진입점 (--selftest 로 진단 모드)
build_exe.py     exe 빌드 (PyInstaller)
make_icon.py     assets/GifBox.ico 생성
```

GUI와 CLI 모두 `pipeline.convert_many()` 하나만 호출합니다.
입력이 파일 경로든 웹 주소든 `sources.py` 가 로컬 파일로 바꿔주므로
뒤쪽 단계는 언제나 로컬 파일만 상대합니다.
진행 상황은 `notify(kind, **data)` 콜백으로 흘러나오고, GUI는 그걸 큐에 넣어
화면에 찍습니다. 변환은 워커 스레드에서 돌아 창이 멈추지 않습니다.

확장 지점은 **소스 → 변환기 → 액션** 세 곳이고, 여기에 값 묶음인 **프리셋**이 붙습니다.

## 기능 추가하는 법

### 0. 새 입력 경로 (유튜브 링크, 클립보드 이미지 …)

`sources.py` 에 추가합니다. `temporary=True` 로 표시하면 처리 후 자동으로 지워지고,
결과 GIF는 `web_outdir` 로 갑니다.

```python
@register_source
class YoutubeSource(Source):
    name = "youtube"
    order = 40                          # 작을수록 먼저 검사 (URL 50, 로컬 100)

    def matches(self, raw):
        return "youtube.com/watch" in raw

    def resolve(self, raw, opts=None, notify=None):
        return [Item(path=download_via_ytdlp(raw), temporary=True, origin=raw)]
```

### 1. 새 입력 포맷

`converters.py` 에 클래스를 하나 추가하면 GUI·CLI·파일 선택 대화상자가 전부 따라옵니다.

```python
@register_converter
class GifsicleConverter(Converter):
    name = "gifsicle"
    label = "gifsicle"
    extensions = frozenset({".gif"})
    priority = 120                      # 클수록 먼저 선택됨

    @classmethod
    def available(cls):
        return shutil.which("gifsicle") is not None

    def convert(self, src, dst, opts, progress=None):
        ...                             # 실패하면 예외를 던지면 됩니다
```

### 2. 변환 후 동작 (업로드, 리사이즈, 알림 …)

`actions.py` 에 추가합니다. `run()` 은 **성공한 결과 전체**를 한 번에 받습니다.

```python
@register_action
class UploadAction(Action):
    name = "upload"
    label = "업로드"
    order = 40                          # 작을수록 먼저 (클립보드 10, 삭제 20)

    def enabled(self, opts):
        return opts.upload              # settings.DEFAULTS 에 "upload": False 추가

    def run(self, results, opts):
        urls = [put(r.dst) for r in results]
        return "☁ %d개 업로드 완료" % len(urls)
```

### 3. 색 바꾸기

`theme.py` 의 `PALETTE` 만 고치면 창 전체가 따라옵니다.

```python
PALETTE["accent"] = "#57F287"      # 블러플 대신 초록으로
```

### 4. 새 프리셋

```python
register_preset(Preset(
    name="twitter", label="트위터용", icon="🐦",
    description="15MB 이하 · 가로 640",
    values={"target_mb": 15, "width": 640, "fps": 15},
))
```

GUI 목록과 CLI `--preset` 에 자동으로 나타납니다.

### 5. 새 설정값

`settings.py` 의 `DEFAULTS` 에 한 줄 추가하면 저장·불러오기·기본값 병합이 자동입니다.
범위 제한이 필요하면 `_RANGES` 에도 넣습니다.
켜고 끄는 항목이면 `settings_dialog.py` 의 `SECTIONS` 에 한 줄 넣는 것으로 끝납니다.
변환 방식에 직접 관계된 값이라면 `gui.py` 의 `_build_options()` 에 위젯을 놓고
`_collect_settings()` 에 한 줄 더합니다.

## 알아둘 점

- **원본 삭제는 변환이 검증된 뒤에만** 실행됩니다. 임시 파일(`.part`)로 먼저 쓰고
  크기가 0이 아닌지 확인한 뒤 이름을 바꾸며, 실패한 파일의 원본은 건드리지 않습니다.
  기본은 영구 삭제가 아니라 휴지통입니다.
- **클립보드는 '파일'로 복사**합니다(CF_HDROP). 이미지(CF_DIB)로 넣으면 받는 쪽이
  첫 프레임짜리 정지 이미지로 붙여넣어 애니메이션이 죽기 때문입니다.
  정지 이미지가 필요하면 설정의 `clipboard_mode` 를 `image` 또는 `both` 로 바꾸세요.
- ffmpeg가 없으면 webp만 변환됩니다(Pillow 폴백). 영상에는 ffmpeg가 필요합니다.
- **드롭 문자열을 `tk.splitlist()` 로 파싱하면 안 됩니다.** Tcl이 백슬래시를
  이스케이프로 해석해서 `C:\new\a.mp4` 의 `\n` 이 줄바꿈으로 바뀝니다.
  `gui.split_drop_list()` 가 중괄호만 보고 직접 자릅니다.
- 썸네일 굽기와 호버용 프레임 읽기는 **워커 스레드**에서 합니다. 스레드는 PIL 이미지만
  만들고, `ImageTk.PhotoImage` 생성은 반드시 메인 스레드에서 합니다(tk 객체는 스레드를
  넘나들면 안 됩니다). 목록이 갱신되면 토큰이 바뀌어 이전 요청 결과는 버려집니다.
- **ttk 는 clam 테마 위에서만 색이 제대로 먹습니다.** 그리고 배경색만 바꾸면
  안 됩니다 — clam 은 테두리를 `lightcolor`/`darkcolor`/`bordercolor` 로 그리는데,
  이 셋이 기본 밝은 회색이라 어두운 배경 위에 흰 테두리가 남습니다.
  `theme.py` 는 `style.configure(".")` 에서 이 셋의 기본값부터 덮습니다.
- **창 크기를 숫자로 박아두지 않습니다.** `_fit_window()` 가 위젯이 요구하는 크기를
  재서 창을 맞춥니다 — 글꼴·DPI 배율에 따라 필요한 크기가 달라지고, 기능을 더 붙여도
  저절로 따라오게 하기 위함입니다.
- 다운로드는 http/https만 받고, Content-Type을 확인하며(웹페이지 주소면 거부),
  `max_download_mb`(기본 200MB)를 넘으면 도중에 끊습니다.
- exe 로 묶으면 `__file__` 기준 경로가 깨집니다. 프로그램 폴더는 `winutil.app_dir()`,
  번들에 같이 넣은 파일은 `winutil.resource_path()` 를 쓰세요.
  onefile 은 실행할 때 임시 폴더에 풀리므로 이 둘이 서로 다른 위치를 가리킵니다.

## 의존성

- Python 3.9+, Pillow
- ffmpeg — 영상 변환용 (`winget install Gyan.FFmpeg`)
- tkinterdnd2 — 창에 끌어다 놓기용 (`pip install tkinterdnd2`, 없어도 창은 동작)
- pyinstaller — exe 빌드용 (`pip install pyinstaller`, 빌드할 때만 필요)

## 라이선스

MIT — [LICENSE](LICENSE) 참고.
