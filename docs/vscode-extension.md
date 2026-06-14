# VS Code 확장 프로그램 및 사용법

이 문서는 reposcore-py 프로젝트에서 Python 개발을 할 때 사용하는 VS Code 확장과 기본 사용 방법을 설명합니다.

Codespaces 환경에서는 Python 개발에 필요한 기본 환경이 준비되어 있으므로, 로컬 환경처럼 Python 설치 과정을 따로 진행할 필요는 없습니다. 이 문서에서는 VS Code에서 Python 코드를 작성하고 확인할 때 필요한 확장과 최소 사용 방법을 정리합니다.

## 이 문서에서 다루는 확장

이 문서에서는 다음 VS Code 확장을 다룹니다.

- Python
  - Python 코드 실행, 디버깅, 인터프리터 선택을 지원합니다.
- Pylance
  - 타입 힌트 기반 정적 분석, 자동 완성, 코드 탐색을 지원합니다.

## Python Extension

Python 확장은 VS Code에서 Python 파일을 실행하고, 인터프리터를 선택하며, 디버깅과 테스트 실행을 지원하는 기본 확장입니다.

### 주요 기능

- Python 파일 실행
- Python 인터프리터 선택
- 디버깅 지원
- 테스트 실행 지원
- Python 관련 명령 팔레트 제공

### Python 파일 실행 방법

Python 파일을 실행하려면 `.py` 파일을 연 뒤 VS Code 오른쪽 위에 있는 실행 버튼을 사용할 수 있습니다.

VS Code에서 `F5`를 누르면 디버깅 실행을 시작할 수 있고, `Ctrl + F5`를 누르면 디버깅 없이 실행할 수 있습니다.

또는 터미널에서 직접 실행할 수도 있습니다.

```bash
python 파일이름.py
```

예를 들어 최상위에 `main.py`가 있다면 다음과 같이 실행할 수 있습니다.

```bash
python main.py
```

### 명령 팔레트에서 Python 명령 실행하기

VS Code의 명령 팔레트를 사용하면 Python 관련 기능을 쉽게 실행할 수 있습니다.

1. `Ctrl + Shift + P`를 누릅니다.
2. `Python`을 입력합니다.
3. 필요한 명령을 선택합니다.

자주 사용하는 명령은 다음과 같습니다.

- `Python: Select Interpreter`
- `Python: Run Python File in Terminal`
- `Python: Create Terminal`

### Python 인터프리터 선택 방법

Python 인터프리터는 현재 프로젝트에서 사용할 Python 실행 환경을 의미합니다.

Codespaces에서는 Python이 기본으로 준비되어 있으므로 보통 별도 설정 없이 사용할 수 있습니다. 다만 인터프리터를 직접 확인하거나 변경해야 할 때는 다음 순서로 진행합니다.

1. `Ctrl + Shift + P`를 누릅니다.
2. `Python: Select Interpreter`를 검색합니다.
3. 목록에서 사용할 Python 인터프리터를 선택합니다.

로컬 환경에서 개발하는 경우에는 Python이 설치되어 있어야 하며, 이때도 같은 방식으로 인터프리터를 선택할 수 있습니다.

## Pylance Extension

Pylance는 Python 코드의 타입 정보를 분석하여 자동 완성, 타입 오류 검사, 코드 탐색 기능을 제공하는 확장입니다.

reposcore-py에서는 타입 힌트를 활용할 예정이므로 Pylance를 함께 사용하는 것이 좋습니다.

### 주요 기능

- 타입 힌트 기반 정적 분석
- 자동 완성
- 함수 매개변수와 반환 타입 확인
- 정의로 이동
- 코드 탐색
- 잘못된 타입 사용 경고

### Type Checking Mode 설정

Pylance의 Type Checking Mode는 타입 힌트를 기준으로 코드의 타입 오류를 얼마나 적극적으로 검사할지 정하는 설정입니다. 이 설정이 `off`로 되어 있으면 타입 힌트를 작성해도 잘못된 타입 사용에 대한 경고를 충분히 받지 못할 수 있습니다.

reposcore-py에서는 타입 힌트를 활용하므로 Type Checking Mode를 `off` 대신 `standard`로 설정하는 것을 권장합니다. `standard`는 일반적인 Python 개발에서 사용하기에 적절한 수준으로 타입 오류를 검사하면서도, 너무 엄격한 규칙으로 개발 흐름을 방해하지 않습니다.

VS Code Settings UI에서는 다음 순서로 설정할 수 있습니다.

1. `Ctrl + ,`를 눌러 Settings를 엽니다.
2. 검색창에 `type checking mode`를 입력합니다.
3. `Python > Analysis: Type Checking Mode` 항목을 찾습니다.
4. 값을 `standard`로 변경합니다.

`settings.json`에 직접 설정하려면 다음 내용을 추가합니다.

```json
{
    "python.analysis.typeCheckingMode": "standard"
}
```

설정을 적용한 뒤에는 Pylance가 타입 힌트를 바탕으로 잘못된 타입 사용을 경고할 수 있습니다. 예를 들어 문자열을 받아야 하는 함수에 숫자를 전달하면 편집기 밑줄이나 `Problems` 패널에서 타입 경고를 확인할 수 있습니다.

### 타입 힌트 확인 예시

다음 함수는 문자열을 입력받고 문자열을 반환한다는 타입 힌트를 가지고 있습니다.

```python
def greet(name: str) -> str:
    return f"Hello, {name}"
```

이 함수에 숫자를 전달하면 Pylance가 타입이 맞지 않을 가능성을 경고할 수 있습니다.

```python
greet(123)
```

`name` 매개변수는 `str` 타입으로 작성되어 있으므로, 숫자인 `123`을 전달하면 타입 힌트와 맞지 않습니다.

타입 경고는 편집기 밑줄 또는 `Problems` 패널에서 확인할 수 있으며, `Ctrl + Shift + M`으로 Problems 패널을 열 수 있습니다.

### 자동 완성 사용

Pylance는 변수와 함수의 타입 정보를 바탕으로 자동 완성을 제공합니다.

예를 들어 문자열 변수에 대해 코드를 작성하면 문자열에서 사용할 수 있는 메서드를 제안합니다.

```python
message: str = "hello"
message.upper()
```

타입 힌트를 작성하면 Pylance가 더 정확한 자동 완성을 제공할 수 있습니다.

### 정의로 이동

함수나 변수 위에 커서를 둔 뒤 다음 기능을 사용할 수 있습니다.

- `F12`: 정의로 이동
- `Ctrl + 클릭`: 정의로 이동
- `Shift + F12`: 참조 찾기

이 기능을 사용하면 여러 파일로 코드가 나뉘어 있을 때 함수나 클래스의 위치를 빠르게 찾을 수 있습니다.

## 권장 사항

새로 작성하는 Python 함수에는 가능한 한 매개변수 타입과 반환 타입을 함께 작성합니다.

```python
def calculate_score(issue_count: int, pr_count: int) -> int:
    return issue_count + pr_count
```

반환값이 없는 함수는 `None`을 사용합니다.

```python
def print_message(message: str) -> None:
    print(message)
```

타입 힌트 작성 방식은 `docs/python-guide.md`의 Python 개발 가이드를 함께 참고합니다.
