using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 世界空間的對話泡：圓角底 ＋（可選）道具圖示 ＋ 文字。
    /// 顧客想買什麼、成交了沒都用它。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版用 Graphics 即時畫圓角矩形（roundRect + fill + stroke），還要手畫小尾巴。
    /// Unity 沒有等價的即時繪圖元件，所以底圖是**程式生成的九宮格 Sprite**（生一次快取）——
    /// 換句話說圓角是烤進貼圖的，用 sliced 模式撐開，任何尺寸都不會變形。
    ///
    /// ⚠️ 文字用 TextMesh 不是 TextMeshPro —— 同 GatherTree 的理由：TextMesh 吃得下
    ///    作業系統的動態字型，中文不用先烘 FontAsset。
    /// </summary>
    public static class SpeechBubble
    {
        const float W = 150f, H = 46f;
        const int Radius = 12;

        /// <summary>
        /// 在 parent 頭頂 headHeight 的地方掛一個對話泡（會先移除舊的）。
        /// </summary>
        /// <param name="parent">要掛在誰身上</param>
        /// <param name="headHeight">這個角色的顯示高度（泡泡擺在它上方）</param>
        /// <param name="icon">左邊的小圖示（null＝只有文字）</param>
        /// <param name="text">內容</param>
        /// <param name="bg">底色</param>
        public static GameObject Show(Transform parent, float headHeight,
                                      Sprite icon, string text, Color32 bg)
        {
            Clear(parent);

            var b = new GameObject("bubble");
            b.transform.SetParent(parent, false);
            b.transform.localPosition = new Vector3(0f, headHeight + 30f, 0f);

            // ⚠️ 角色往右走時整個節點會被翻面（VillagerAnim.SetFacing），
            //    泡泡要反轉回來，不然文字會變鏡像。
            float px = parent.localScale.x;
            if (px < 0f) b.transform.localScale = new Vector3(-1f, 1f, 1f);

            var back = new GameObject("bg");
            back.transform.SetParent(b.transform, false);
            var bsr = back.AddComponent<SpriteRenderer>();
            bsr.sprite = RoundRect();
            bsr.drawMode = SpriteDrawMode.Sliced;
            bsr.size = new Vector2(W, H);
            bsr.color = bg;
            bsr.sortingOrder = 9500;

            float textX = 0f;
            if (icon != null)
            {
                var i = new GameObject("icon");
                i.transform.SetParent(b.transform, false);
                float k = 32f / Mathf.Max(icon.rect.width, icon.rect.height);
                i.transform.localPosition = new Vector3(-W / 2f + 24f, 0f, 0f);
                i.transform.localScale = new Vector3(k, k, 1f);
                var isr = i.AddComponent<SpriteRenderer>();
                isr.sprite = icon;
                isr.sortingOrder = 9501;
                textX = 20f;
            }

            MakeText(b.transform, text, new Vector3(textX, 0f, 0f));
            return b;
        }

        /// <summary>移除某個角色身上的對話泡。</summary>
        public static void Clear(Transform parent)
        {
            var old = parent.Find("bubble");
            if (old != null) Object.Destroy(old.gameObject);
        }

        // ──────────── 內部 ────────────

        static void MakeText(Transform parent, string str, Vector3 localPos)
        {
            var go = new GameObject("text");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos + new Vector3(0f, 0f, -0.01f);

            var tm = go.AddComponent<TextMesh>();
            tm.text = str;
            tm.fontSize = 36;
            tm.characterSize = 4.5f;          // ≈ 16px 高（見 GatherTree 的換算說明）
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = new Color32(240, 236, 228, 255);

            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = 9502;
        }

        static Sprite roundRect;

        /// <summary>圓角矩形底圖（程式生成一次，之後共用）。九宮格邊界設在圓角外。</summary>
        static Sprite RoundRect()
        {
            if (roundRect != null) return roundRect;

            int n = Radius * 2 + 4;                     // 剛好容得下兩個圓角 + 中間 4px
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    // 距離最近角落的圓心多遠 —— 在半徑內就是不透明
                    float cx = Mathf.Clamp(x, Radius, n - 1 - Radius);
                    float cy = Mathf.Clamp(y, Radius, n - 1 - Radius);
                    float d = Vector2.Distance(new Vector2(x, y), new Vector2(cx, cy));
                    float a = Mathf.Clamp01(Radius - d + 0.5f);      // 邊緣抗鋸齒
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();

            roundRect = Sprite.Create(tex, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 1f,
                                      0, SpriteMeshType.FullRect,
                                      new Vector4(Radius, Radius, Radius, Radius));   // 九宮格邊界
            return roundRect;
        }
    }
}
