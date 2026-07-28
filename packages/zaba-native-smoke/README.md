# zaba-native-smoke

Minimal Cython extension used to prove that a runtime-matched Android native
module loads and crosses the Python/C boundary. It intentionally has **no pure
Python fallback**: successful import and `runtime_info()["native_loaded"]` are
evidence that the compiled extension is active.

```python
import zaba_native_smoke
assert zaba_native_smoke.add(20, 22) == 42
assert zaba_native_smoke.runtime_info()["native_loaded"] is True
```
