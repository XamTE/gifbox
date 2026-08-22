# -*- coding: utf-8 -*-
"""GifBox — webp/mp4 등을 GIF로 바꾸는 작은 도구.

확장 지점은 두 곳입니다.

1. 입력 포맷을 늘리려면  : gifbox/converters.py 에 Converter 서브클래스를 만들고
                          @register_converter 를 붙입니다.
2. 변환 후 동작을 늘리려면: gifbox/actions.py 에 Action 서브클래스를 만들고
                          @register_action 을 붙입니다. (클립보드 복사·원본 삭제가 이 방식)

새 설정값은 gifbox/settings.py 의 DEFAULTS 에 한 줄 추가하면
저장/불러오기/GUI 연결이 자동으로 따라옵니다.
"""

__version__ = "1.0.0"

APP_NAME = "GifBox"
