using UnityEngine;
using UnityEngine.UIElements;

namespace WitchShop.UI
{
    /// <summary>
    /// 中文字型。
    ///
    /// ⚠️ **這是 Unity 做中文遊戲一定會踩的坑。**
    ///    UI Toolkit 的預設字型（Unity 6 是 Inter）**完全沒有中文字**，所以
    ///    「背包」「藥草」這些字會直接變成空白或豆腐方塊 —— 而且不會報任何錯，
    ///    畫面就是一片空。Cocos 那邊跑在瀏覽器裡、直接吃系統字型，所以從來沒遇過。
    ///
    /// ── 為什麼要把字型檔收進專案 ──────────────────────────────
    /// 一開始的做法是 Font.CreateDynamicFontFromOSFont() 跟作業系統借微軟正黑體。
    /// 那在編輯器裡沒問題，但有兩個致命限制：
    ///   1. **網頁版（WebGL）完全不能用** —— 瀏覽器裡沒有「作業系統字型」可以借，
    ///      所有中文會靜默消失。
    ///   2. 就算只出 Windows 版，也要賭玩家電腦上剛好有那套字。
    ///   3. 把 Windows 的字型檔包進遊戲散布是**授權問題**（msjh.ttc 不可散布）。
    ///
    /// 所以現在改成優先讀專案裡的 Resources/ui/fonts/NotoSansTC.ttf ——
    /// 那是 **SIL Open Font License**，可以合法隨遊戲散布。
    /// OS 字型只留作「專案裡的字型檔不見了」的退路。
    /// </summary>
    public static class CjkFont
    {
        /// <summary>專案內字型（可散布，網頁版唯一能用的來源）。</summary>
        const string BundledPath = "ui/fonts/NotoSansTC";

        /// <summary>退路：跟作業系統借（只在編輯器/桌面版有效，網頁版一定失敗）。</summary>
        static readonly string[] OsCandidates =
        {
            "Noto Sans TC", "Microsoft JhengHei", "Microsoft YaHei",
            "PMingLiU", "MingLiU", "SimSun",
        };

        static Font cached;
        static bool tried;

        /// <summary>取得一套有中文字的字型；找不到回 null。</summary>
        public static Font Get()
        {
            if (tried) return cached;
            tried = true;

            // ① 專案內的 Noto（唯一在網頁版也能用的來源）
            cached = Resources.Load<Font>(BundledPath);
            if (cached != null)
            {
                Debug.Log($"[CjkFont] 使用專案內字型：{BundledPath}");
                return cached;
            }

            Debug.LogWarning($"[CjkFont] 找不到 Resources/{BundledPath} —— " +
                             "退回跟作業系統借字型。⚠️ 網頁版這條路是行不通的，中文會消失。");

            // ② 退路：OS 字型
            var installed = Font.GetOSInstalledFontNames();
            foreach (var want in OsCandidates)
                foreach (var have in installed)
                {
                    if (!have.StartsWith(want, System.StringComparison.OrdinalIgnoreCase)) continue;
                    cached = Font.CreateDynamicFontFromOSFont(have, 20);
                    if (cached != null)
                    {
                        Debug.Log($"[CjkFont] 使用系統字型：{have}");
                        return cached;
                    }
                }

            Debug.LogError("[CjkFont] 找不到任何中文字型，UI 上的中文會顯示不出來。");
            return null;
        }

        /// <summary>把中文字型套到一棵 UI 樹上（子元素會繼承）。</summary>
        public static void Apply(VisualElement root)
        {
            var f = Get();
            if (f != null) root.style.unityFontDefinition = new StyleFontDefinition(f);
        }
    }
}
