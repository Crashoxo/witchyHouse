#!/bin/bash
# 離線型別檢查（Git Bash）：不開 Unity 就編一次所有 C#，只看編不編得過。
#
#   bash tools/typecheck.sh
#
# ⚠️ 為什麼需要它：**Unity 開著的時候專案是鎖住的**，`Unity.exe -batchmode -quit` 會
#    在印完命令列參數之後直接以 exit code 1 結束，log 只有 60 行、**不會有任何錯誤訊息** ——
#    看起來就像「編過了」。改完程式要驗，要嘛關掉 Unity 跑 batchmode，要嘛跑這支。
#
# 用 Unity 內附的 Roslyn 直接編，輸出丟到暫存檔；分兩趟：Assets/Scripts（執行期）
# 與 Assets/Editor（多引用 UnityEditor 與前一趟的產物），跟 Unity 的組件切分一致。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNITY="${UNITY_DATA:-/c/Program Files/Unity/Hub/Editor/6000.6.0f1/Editor/Data}"
CSC="$UNITY/DotNetSdk/sdk/8.0.318/Roslyn/bincore/csc.dll"
OUT="${TMPDIR:-/tmp}/witch-typecheck"
mkdir -p "$OUT"
w() { cygpath -w "$1"; }

[ -f "$CSC" ] || { echo "找不到 Roslyn：$CSC（Unity 版本不同就設 UNITY_DATA 環境變數）"; exit 2; }

pass() {   # $1=輸出名 $2=來源資料夾 $3...=額外引用
  local name="$1" src="$2"; shift 2
  local rsp="$OUT/$name.rsp"
  {
    echo "-target:library"; echo "-nologo"; echo "-langversion:9.0"; echo "-nostdlib+"
    echo "-out:\"$(w "$OUT/$name.dll")\""
    echo "-r:\"$(w "$UNITY/NetStandard/ref/2.1.0/netstandard.dll")\""
    for extra in "$@"; do echo "-r:\"$(w "$extra")\""; done
    for f in "$UNITY/Managed/UnityEngine/"UnityEngine*.dll; do echo "-r:\"$(w "$f")\""; done
    find "$src" -name "*.cs" | while read -r f; do echo "\"$(w "$f")\""; done
  } > "$rsp"
  "$UNITY/DotNetSdk/dotnet.exe" "$CSC" "@$(w "$rsp")"
}

pass runtime "$ROOT/Assets/Scripts" || exit 1
pass editor "$ROOT/Assets/Editor" "$UNITY/Managed/UnityEditor.dll" "$OUT/runtime.dll" || exit 1
echo "OK —— 編得過（上面若只有 CS0618 之類的警告就沒事）"
