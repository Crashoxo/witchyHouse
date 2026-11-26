using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 右上角的時鐘 HUD：盤面 ＋ 時針/分針 ＋ 日月徽章 ＋ 季節緞帶 ＋ 月/日數字 ＋ 時刻文字。
    ///
    /// ⚠️ 這裡**只負責顯示**。時間本身由 TimeDriver 推進（見 TimeSystem 的移植註記）——
    ///    原版是讓這個 HUD 順便驅動時間的，那樣時鐘沒生出來整個遊戲的時間就停了。
    ///
    /// 版面比例（D、MedallionY、RibbonY…）是原專案對切好的 face.png 目視量出來的，
    /// 原封照抄，換美術才需要動。
    ///
    /// 外觀：**鐘面本身（ui/clock/*）兩種外觀都一樣、不動**。像素外觀（<see cref="UiSkin.On"/>）只換盤面底下那兩行字：
    /// 改成靠右疊放的兩顆深木膠囊（時刻大、日期小；Skin8.uss 的 .sk-clock-*），跟工具列、下排背包列同一個語彙。
    /// 外觀關著時照舊是直接印在畫面上的兩行字（HudExtraStyle 的 .clock-text／.clock-date）。
    /// </summary>
    public class ClockHud : MonoBehaviour
    {
        public static ClockHud Instance { get; private set; }

        public static ClockHud Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("ClockHud");
            DontDestroyOnLoad(go);
            return go.AddComponent<ClockHud>();
        }

        // ── 版面（抄自原版 Clock.ts）────────────────────────────
        const float D = 152f;                  // 盤面顯示寬
        const float Aspect = 670f / 674f;      // face.png 高/寬
        const float Dh = D * Aspect;
        const float R = D / 2f;

        /// <summary>
        /// 指針美術。⚠️ 依「時鐘慣例」指派，**不是依檔名** —— 時針用華麗矛形（hand-min）、
        /// 分針用細長（hand-day）；剩下的 hand-hour（樸素短針）不用。
        /// AnchorY＝樞軸在圖上的位置（從底部算的比例）；Reach＝指尖伸到半徑的幾成。
        /// </summary>
        struct HandSpec { public string Key; public float W, H, AnchorY, Reach; }

        static readonly HandSpec Hour = new() { Key = "hand-min", W = 37f, H = 151f, AnchorY = 0.133f, Reach = 0.46f };
        static readonly HandSpec Min  = new() { Key = "hand-day", W = 35f, H = 192f, AnchorY = 0.089f, Reach = 0.68f };

        const float MedallionY = 0.39f;   // 頂端日月徽章：盤心往上 0.39*Dh
        const float BoxY = -0.05f;        // 月/日數字框中心：盤心往下 0.05*Dh
        const float MonthX = -0.135f;
        const float DayX = 0.145f;
        const float IconH = 22f;
        const float RibbonY = 0.284f;     // 盤面上方那條米色緞帶
        const float SeasonH = 26f;

        UIDocument doc;
        VisualElement dial, hourHand, minHand, sun, moon, seasonIcon;
        Label monthLabel, dayLabel, timeLabel, dateLabel;
        int lastMonth = -1, lastDay = -1, lastSeason = -1;
        bool built;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 5;          // 在面板之下、遊戲畫面之上
            if (doc.panelSettings == null)
            {
                Debug.LogError("[ClockHud] 找不到 Resources/ui/UIPanelSettings");
                return;
            }
            GameArt.Preload();
            GameArt.OnReady(Build);
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        void Build()
        {
            if (built) return;
            var root = doc.rootVisualElement;
            if (root == null) return;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關 UiSkin.Enabled）：只影響盤面底下的時刻／日期
            root.pickingMode = PickingMode.Ignore;
            CjkFont.Apply(root);

            var layer = new VisualElement();
            layer.AddToClassList("clock-layer");
            layer.pickingMode = PickingMode.Ignore;
            root.Add(layer);

            dial = new VisualElement();
            dial.AddToClassList("clock");
            dial.pickingMode = PickingMode.Ignore;
            layer.Add(dial);

            var face = new VisualElement();
            face.AddToClassList("clock-face");
            SetImage(face, GameArt.ClockPart("face"));
            dial.Add(face);

            // 日月徽章（盤面頂端；白天太陽、夜晚月亮）
            sun = AddIcon(GameArt.ClockPart("sun"), IconH, IconH, MedallionY);
            moon = AddIcon(GameArt.ClockPart("moon"), IconH * 52f / 64f, IconH, MedallionY);

            // 季節圖標坐在盤面上方那條空的米色緞帶上
            seasonIcon = AddIcon(null, SeasonH, SeasonH, RibbonY);

            // ⚠️ 指針要**先**加、數字**後**加 —— UI Toolkit 是後加的畫在上面。
            //    反過來的話指針底部那顆圓頭會整個蓋住月/日那兩個格子（原版 Clock.ts
            //    的建構順序就是 盤面→指針→日月→季節→數字，我一開始弄反了）。
            hourHand = AddHand(Hour);
            minHand = AddHand(Min);

            // 月 / 日 數字（盤面中央那兩個小格子）
            monthLabel = AddNumber(MonthX);
            dayLabel = AddNumber(DayX);

            // 盤面上的月/日是兩個小數字，不夠清楚 —— 底下再給時刻與一行完整日期
            timeLabel = new Label { pickingMode = PickingMode.Ignore };
            dateLabel = new Label { pickingMode = PickingMode.Ignore };
            if (UiSkin.On)
            {
                // 像素外觀：盤面正下方、靠右疊兩顆膠囊（寬度跟著字）
                var info = new VisualElement { pickingMode = PickingMode.Ignore };
                info.AddToClassList("sk-clock-info");
                dial.Add(info);
                timeLabel.AddToClassList("sk-clock-time");
                dateLabel.AddToClassList("sk-clock-date");
                info.Add(timeLabel);
                info.Add(dateLabel);
            }
            else
            {
                timeLabel.AddToClassList("clock-text");
                dial.Add(timeLabel);
                dateLabel.AddToClassList("clock-date");
                dial.Add(dateLabel);
            }

            built = true;
            Refresh();
        }

        void Update()
        {
            if (!built) return;
            Refresh();
        }

        void Refresh()
        {
            // ⚠️ 旋轉方向跟 Cocos 相反：Cocos 的 angle 正向是逆時針（所以原版寫 -fraction*360），
            //    UI Toolkit 的 rotate 正向是順時針（螢幕座標 y 向下），所以這裡不用取負。
            SetAngle(hourHand, TimeSystem.HourFraction * 360f);
            SetAngle(minHand, TimeSystem.MinuteFraction * 360f);

            bool night = TimeSystem.IsNight;
            if (sun != null) sun.style.display = night ? DisplayStyle.None : DisplayStyle.Flex;
            if (moon != null) moon.style.display = night ? DisplayStyle.Flex : DisplayStyle.None;

            int m = TimeSystem.Month, d = TimeSystem.Day, s = TimeSystem.Season;
            if (m != lastMonth) { lastMonth = m; monthLabel.text = m.ToString(); }
            if (d != lastDay) { lastDay = d; dayLabel.text = d.ToString(); }
            if (s != lastSeason) { lastSeason = s; SetImage(seasonIcon, GameArt.SeasonIcon(s)); }

            timeLabel.text = TimeSystem.ClockText();
            dateLabel.text = TimeSystem.DateTextFull();     // 第 N 年 X 月 X 日（季）
        }

        // ──────────── 建構小工具 ────────────

        static void SetImage(VisualElement el, Sprite sp)
        {
            if (el == null) return;
            el.style.backgroundImage = sp != null ? new StyleBackground(sp) : StyleKeyword.None;
        }

        /// <summary>擺一個以盤心為基準、往上 fracY*Dh 的小圖示。</summary>
        VisualElement AddIcon(Sprite sp, float w, float h, float fracY)
        {
            var el = new VisualElement();
            el.AddToClassList("clock-icon");
            el.style.width = w;
            el.style.height = h;
            el.style.marginLeft = -w / 2f;                    // left:50% 之後往左推半個寬 → 水平置中
            el.style.top = Dh / 2f - fracY * Dh - h / 2f;
            SetImage(el, sp);
            dial.Add(el);
            return el;
        }

        Label AddNumber(float fracX)
        {
            // 尺寸照原版：寬 0.20*D、高 0.16*Dh（＝字級 23 的行高）
            const float w = 0.20f * D, h = 0.16f * Dh;
            var l = new Label();
            l.AddToClassList("clock-num");
            l.style.width = w;
            l.style.height = h;
            l.style.left = D / 2f + fracX * D - w / 2f;
            l.style.top = Dh / 2f - BoxY * Dh - h / 2f;
            dial.Add(l);
            return l;
        }

        /// <summary>
        /// 一根指針。
        ///
        /// 圖的樞軸不在中心，而在底部那顆圓頭上（AnchorY，從底部算的比例）。
        /// 所以要：
        ///   1. 依 Reach 算出顯示高度 —— 指尖剛好伸到 Reach × 半徑
        ///   2. 把元素擺成「樞軸點落在盤心」
        ///   3. transform-origin 設在樞軸點，旋轉才會繞盤心轉
        /// </summary>
        VisualElement AddHand(HandSpec spec)
        {
            // 指尖到樞軸的長度 = (1 - AnchorY) × 顯示高 = Reach × R
            float dispH = spec.Reach * R / (1f - spec.AnchorY);
            float dispW = dispH * (spec.W / spec.H);
            float pivotFromTop = (1f - spec.AnchorY) * dispH;   // 樞軸離圖頂端多遠

            var el = new VisualElement();
            el.AddToClassList("clock-hand");
            el.style.width = dispW;
            el.style.height = dispH;
            el.style.marginLeft = -dispW / 2f;
            el.style.top = Dh / 2f - pivotFromTop;             // 讓樞軸落在盤心
            el.style.transformOrigin = new StyleTransformOrigin(
                new TransformOrigin(new Length(50f, LengthUnit.Percent),
                                    new Length(pivotFromTop / dispH * 100f, LengthUnit.Percent)));
            SetImage(el, GameArt.ClockPart(spec.Key));
            dial.Add(el);
            return el;
        }

        static void SetAngle(VisualElement el, float deg)
        {
            if (el == null) return;
            el.style.rotate = new StyleRotate(new Rotate(new Angle(deg, AngleUnit.Degree)));
        }
    }
}
