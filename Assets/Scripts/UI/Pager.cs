using System;
using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 清單翻頁（2026-11-27，使用者：「清單類的面板都要固定高度，東西太多就翻頁，不要捲軸」）。
    ///
    /// 一個 Pager ＝ 兩塊元素，面板自己決定擺哪：
    ///   <see cref="Body"/>：放這一頁的列。**固定高度**（建構時給的 bodyHeight，inline 的 height／min／max 三個一起鎖），
    ///                       overflow 隱藏 —— 面板的大小因此跟「有幾列、在哪個分頁」完全無關。
    ///   <see cref="Bar"/>： [◀][3 / 5][▶]。只有一頁時整條 visibility: hidden（**位置照留**，旁邊的東西不會跳）；
    ///                       第一頁的 ◀、最後一頁的 ▶ 停用（skin8 的 page-*-off 灰鈕）。圖在 skin8/page-*（gen_ui_skin.py 第五輪），
    ///                       數字用一般字；不寫任何說明文字（提示用圖不用字）。
    ///
    /// ── 用法 ─────────────────────────────────────────────────
    ///   pager = new Pager(每頁幾列, 每頁幾列 × 列距, Refresh);    // Refresh＝面板自己的重畫
    ///   清單區.Add(pager.Body);  底列.Add(pager.Bar);
    ///   Refresh 裡：pager.Render(總數, i => 做第 i 列(), "這一類目前沒有東西");
    ///   切分頁／重新打開：pager.Reset() 再 Refresh（回第 1 頁）。
    ///   東西變多變少（存入一個、賣掉一個）：**不要** Reset，直接 Refresh —— Render 只會把頁碼夾回範圍內
    ///   （最後一頁的最後一個沒了 → 退到新的最後一頁，其他情況留在原頁）。
    ///   面板的 Update（開著的時候）叫 <see cref="HandleKeys"/>：←／→、A／D 翻頁。
    ///
    /// ── 翻頁的輸入 ───────────────────────────────────────────
    ///   點箭頭、滑鼠滾輪（Body 與 Bar 上；0.2 秒節流，觸控板一下會送一大串）、←／→、A／D（由面板的 Update 轉呼叫，
    ///   所以只有「開著的那個面板」會動 —— 這些面板都是 modal，同時只會開一個）。翻到頭不循環、不出聲；翻成功響 `page`。
    ///   箭頭是 focusable=false 的 Button（Space／Enter 不會「再按一次」）。
    ///
    /// ⚠️ 列是每頁重建的：列上的 hover／tooltip（UiSkin.Tip）／按鈕都是 make(i) 新建的，照常運作；
    ///    但被 Clear 掉的元素不會送 PointerLeave —— 面板有浮動說明的話，Refresh 時自己 UiSkin.HideTip。
    /// ⚠️ 列距（每列高＋下邊距）要跟 uss 對得上：像素外觀的清單列是 `.sk .row` 高 57 ＋ margin-bottom 3 ＝ 60。
    ///    舊外觀（UiSkin.Enabled=false）的列比較矮，同樣的頁容量一定放得下。
    /// </summary>
    public sealed class Pager
    {
        /// <summary>滾輪翻頁的最短間隔（秒，真實時間）。</summary>
        const float WheelGap = 0.2f;

        /// <summary>這一頁的列放這裡（固定高度、超出的隱藏）。</summary>
        public VisualElement Body { get; }
        /// <summary>[◀][n / m][▶]。</summary>
        public VisualElement Bar { get; }

        /// <summary>目前第幾頁（0 起算）。</summary>
        public int Page => page;
        /// <summary>總頁數（至少 1）。</summary>
        public int Pages => pages;
        /// <summary>一頁幾個。</summary>
        public int PerPage { get; private set; }
        /// <summary>滑鼠在翻頁鈕這條上（每日結算「點一下關閉」要讓開）。</summary>
        public bool PointerOverBar { get; private set; }

        readonly Button prev, next;
        readonly Label num;
        readonly Action rerender;
        int page, pages = 1;
        float wheelReadyAt;

        /// <param name="perPage">一頁幾個（列數，或格子數）。</param>
        /// <param name="bodyHeight">Body 的固定高度；≤0 表示高度交給 uss／flex（例如任務簿撐滿捲軸），只鎖 overflow。</param>
        /// <param name="rerender">翻頁後要重畫：通常就是面板的 Refresh（它會再叫 <see cref="Render"/>）。</param>
        /// <param name="body">現成的容器（例如 UXML 裡的那一塊）；null 就新建一個。</param>
        public Pager(int perPage, float bodyHeight, Action rerender, VisualElement body = null)
        {
            PerPage = Mathf.Max(1, perPage);
            this.rerender = rerender;

            Body = body ?? new VisualElement();
            Body.AddToClassList("pg-body");
            if (bodyHeight > 0f)
            {
                Body.style.height = bodyHeight;
                Body.style.minHeight = bodyHeight;
                Body.style.maxHeight = bodyHeight;
            }
            Body.style.flexShrink = 0;
            Body.style.overflow = Overflow.Hidden;
            Body.RegisterCallback<WheelEvent>(OnWheel);

            Bar = new VisualElement();
            Bar.AddToClassList("pg-bar");
            Bar.RegisterCallback<WheelEvent>(OnWheel);
            Bar.RegisterCallback<PointerEnterEvent>(_ => PointerOverBar = true);
            Bar.RegisterCallback<PointerLeaveEvent>(_ => PointerOverBar = false);

            // 像素外觀：箭頭畫在圖裡、按鈕文字留空；舊外觀退回 < >（字型一定有的 ASCII）
            bool skin = UiSkin.On;
            prev = new Button(() => Step(-1)) { text = skin ? "" : "<", focusable = false };
            prev.AddToClassList("pg-arrow");
            prev.AddToClassList("pg-arrow--prev");
            Bar.Add(prev);

            num = new Label();
            num.AddToClassList("pg-num");
            num.pickingMode = PickingMode.Ignore;
            Bar.Add(num);

            next = new Button(() => Step(1)) { text = skin ? "" : ">", focusable = false };
            next.AddToClassList("pg-arrow");
            next.AddToClassList("pg-arrow--next");
            Bar.Add(next);

            UpdateBar();
        }

        /// <summary>回第 1 頁（切分頁、重新打開面板時）。不重畫 —— 呼叫端接著自己 Refresh。</summary>
        public void Reset() => page = 0;

        /// <summary>
        /// 改一頁的容量（例如佈置托盤照實際寬度算一排放幾格、手札的村民列比較高）。
        /// 盡量讓「目前這頁的第一個」還留在畫面上。不重畫。
        /// </summary>
        public void SetPerPage(int n)
        {
            n = Mathf.Max(1, n);
            if (n == PerPage) return;
            int first = page * PerPage;
            PerPage = n;
            page = first / n;
        }

        /// <summary>
        /// 把第 <see cref="Page"/> 頁畫進 <see cref="Body"/>：清掉、夾頁碼、對這頁的每個索引叫 <paramref name="make"/>。
        /// <paramref name="total"/> 是 0 時放一行置中的 <paramref name="emptyText"/>（class 用 <paramref name="emptyClass"/>）。
        /// </summary>
        public void Render(int total, Func<int, VisualElement> make, string emptyText = null, string emptyClass = "empty-msg")
        {
            total = Mathf.Max(0, total);
            pages = Mathf.Max(1, (total + PerPage - 1) / PerPage);
            page = Mathf.Clamp(page, 0, pages - 1);

            Body.Clear();
            Body.EnableInClassList("pg-body--empty", total == 0);
            if (total == 0)
            {
                if (!string.IsNullOrEmpty(emptyText))
                {
                    var msg = new Label(emptyText);
                    if (!string.IsNullOrEmpty(emptyClass)) msg.AddToClassList(emptyClass);
                    msg.AddToClassList("pg-empty");
                    Body.Add(msg);
                }
            }
            else
            {
                int end = Mathf.Min(total, (page + 1) * PerPage);
                for (int i = page * PerPage; i < end; i++)
                {
                    var el = make?.Invoke(i);
                    if (el != null) Body.Add(el);
                }
            }
            UpdateBar();
        }

        /// <summary>往前／往後一頁。到頭就不動（不循環、不出聲）。</summary>
        public void Step(int dir)
        {
            int target = page + (dir < 0 ? -1 : 1);
            if (target < 0 || target >= pages) return;
            page = target;
            Sfx.Play("page");                                       // 音效：翻頁的紙張「唰」（同一幀的 click 音會讓給它）
            if (rerender != null) rerender();
            else UpdateBar();
        }

        /// <summary>面板開著時每幀叫：←／A 上一頁，→／D 下一頁。</summary>
        public void HandleKeys()
        {
            if (pages < 2) return;
            if (Input.GetKeyDown(KeyCode.LeftArrow) || Input.GetKeyDown(KeyCode.A)) Step(-1);
            else if (Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.D)) Step(1);
        }

        void OnWheel(WheelEvent e)
        {
            e.StopPropagation();
            if (pages < 2 || Mathf.Abs(e.delta.y) < 0.01f || Time.unscaledTime < wheelReadyAt) return;
            wheelReadyAt = Time.unscaledTime + WheelGap;
            Step(e.delta.y > 0 ? 1 : -1);
        }

        void UpdateBar()
        {
            num.text = $"{page + 1} / {pages}";
            prev.SetEnabled(page > 0);
            next.SetEnabled(page < pages - 1);
            // 只有一頁：整條藏起來但位置照留（visibility，不是 display）
            Bar.style.visibility = pages > 1 ? Visibility.Visible : Visibility.Hidden;
            if (pages < 2) PointerOverBar = false;
        }
    }
}
