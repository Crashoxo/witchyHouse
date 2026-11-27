using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 家裡（藥水室 brew）的佈置模式：按 **R** 進出（**Esc** 也出），把自己買的燈、家具、裝飾、地毯擺在房間的空地上。
    /// 房間原本的家具（床、鍋爐、壁爐、書櫃、桌子、衣櫃、木箱、三張地毯…）是房間的一部分，不能搬。
    /// 由 BrewRoom.BuildSvgRoom 叫起來（開關 <see cref="Enabled"/>）；資料在 <see cref="HomeLayout"/>、畫面在 <see cref="HomeFurnishings"/>、
    /// 規則在 <see cref="HomePlacement"/>。
    ///
    /// ── 操作（跟店裡佈置／後花園搬花圃同一套手感）──
    ///   · 下面的托盤（UI/ShopRoomTray 的 Home 模式）列「還沒擺」而且能擺家裡的東西（陳列桌、貨架、販售桌不列）。
    ///     在托盤格上按住往房間拖 → 放開就擺；或點一下托盤格 → 東西黏在滑鼠上，再點地板擺下去。
    ///   · 房間裡擺好的：按住拖去別處；拖回托盤上放開＝收回托盤；右鍵＝收回托盤。
    ///   · 拿著的（或剛擺好、剛點過的那件）按 **F** 左右翻面（同店裡的轉向鍵）。
    ///   · 拿著東西時：右鍵／Esc＝放回去（從托盤拿的回托盤、搬到一半的回原位）。
    ///   · 自由擺，但軟吸附到地板 8px 的點上（HomePlacement.Snap，看不到格線）。腳下的佔地預覽：綠＝可以、紅＝不行，
    ///     同時把門口、互動點前面、貓窩這些「不能擺」的地方用淡紅色標出來（地毯只標貓窩）。
    ///   · 放不下：deny 音＋東西抖一下，托盤提示列亮 [×][原因圖]（不跳句子）。每一步都當下存檔，沒有「取消還原」（同後花園）。
    ///   · 佈置中女巫不走、E 不作用（Interact.Suspended 看 HomeArrange.Busy → 世界裡的互動提示全收、E 誰都不給）、貓停在原地；
    ///     開著面板（UIState.ModalOpen）不吃輸入；睡覺過場（也是 ModalOpen）一來就收工。
    /// </summary>
    public class HomeArrange : MonoBehaviour
    {
        /// <summary>功能開關：false ＝ 家裡不能擺東西（家裡存的擺設全部當成「還沒擺」，店裡托盤拿得到）。</summary>
        public static bool Enabled = true;

        public static HomeArrange Instance { get; private set; }

        /// <summary>家裡佈置中（PlayerController、RoomCat、CornerHud 看這個）。</summary>
        public static bool Busy => Instance != null && Instance.Editing;

        public bool Editing { get; private set; }

        public static HomeArrange Ensure(Transform parent)
        {
            if (Instance != null) return Instance;
            var go = new GameObject("HomeArrange");
            go.transform.SetParent(parent, false);
            return go.AddComponent<HomeArrange>();
        }

        Camera cam;
        static HomeFurnishings View => HomeFurnishings.Instance;

        // ── 手上拿著的 ──
        bool holding;
        int heldIndex = -1;            // ≥0：搬房間裡第幾件；-1：從托盤拿出來的
        string heldId;
        bool heldFlip, origFlip;
        GameObject heldGo;             // 搬的那件＝房間裡的物件；托盤拿的＝自己生的暫時物件
        Vector2 grabOffset, heldPos, origPos;
        bool heldByButton;             // true＝按著滑鼠拖；false＝點了托盤之後黏在滑鼠上
        bool leftTray;                 // 從托盤拿的：滑鼠離開過托盤沒（沒離開就放開＝「點一下」）
        int heldFrame;
        bool heldOverTray;
        HomeBlock heldBlock = HomeBlock.Ok;
        List<HomeShape> others;
        int selected = -1;             // F 翻面作用在它（剛擺好／剛點過的那件）

        // ── 畫面 ──
        SpriteRenderer ghost, zones;
        string ghostKey;
        Sprite zonesAll, zonesCat;
        float flashUntil;
        GameObject shakeGo;
        Vector3 shakeBase;
        float shakeT0;

        static readonly Color GhostOk = new(0.25f, 1f, 0.4f, 0.8f);
        static readonly Color GhostBad = new(1f, 0.18f, 0.18f, 0.85f);
        static readonly Color ZoneCol = new(1f, 0.3f, 0.28f, 0.55f);
        static readonly Color TintOk = new(0.82f, 1f, 0.84f, 1f);
        static readonly Color TintBad = new(1f, 0.6f, 0.58f, 1f);

        // ── 排序 ──
        const int OrderZones = -9450;     // 房間底圖與原本的地毯（-9500）之上、自己的地毯（-9000）之下
        const int OrderGhost = -8950;     // 自己的地毯之上、影子（-8500）之下
        const int OrderHeld = 7600;       // 拿著的東西蓋過所有家具與人（光暈 8000 之下）

        const float ShakeSecs = 0.35f;
        const float FlashSecs = 1.4f;

        void Awake() { Instance = this; cam = Camera.main; }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            var tray = UI.ShopRoomTray.Instance;
            if (tray != null && Editing)
            {
                tray.onPress = null;
                tray.Hide();
            }
        }

        // ──────────── 每幀 ────────────

        void Update()
        {
            if (!Enabled || View == null) return;

            if (Editing && UIState.ModalOpen)
            {
                // 開了面板／睡覺過場：手上的放回去、收工
                if (holding) CancelHold(false);
                Exit();
                return;
            }

            // R 切換。⚠️ 開著別的面板時不吃
            if (!UIState.ModalOpen && Input.GetKeyDown(KeyCode.R))
            {
                if (Editing)
                {
                    // 拿著東西按 R：放得下就照「放下」處理（同後花園），放不下就放回去
                    if (holding && heldBlock == HomeBlock.Ok && !heldOverTray && !float.IsNaN(heldPos.x)) TryDrop();
                    Exit();
                }
                else Enter();
                return;
            }
            if (!Editing) return;

            if (Input.GetKeyDown(KeyCode.Escape))
            {
                if (holding) CancelHold(true); else Exit();
                return;
            }
            if (Input.GetKeyDown(KeyCode.F))
            {
                if (holding) FlipHeld(); else if (selected >= 0) FlipSelected();
            }

            if (holding)
            {
                if (Input.GetMouseButtonDown(1)) { CancelHold(true); return; }
                MoveHeld();
                if (heldByButton)
                {
                    if (!Input.GetMouseButton(0)) Release();
                }
                else if (Input.GetMouseButtonDown(0) && Time.frameCount != heldFrame)
                {
                    if (OverTray()) CancelHold(true);        // 點回托盤＝放回去
                    else TryDrop();
                }
                return;
            }

            if (Input.GetMouseButtonDown(1)) { StoreUnderMouse(); return; }
            if (Input.GetMouseButtonDown(0)) BeginDragUnderMouse();
        }

        void LateUpdate()
        {
            if (!Editing) return;
            float t = Time.unscaledTime;
            UpdateShake(t);
            if (flashUntil > 0f && t > flashUntil) { flashUntil = 0f; UpdateHint(); }
            if (ghost != null && ghost.gameObject.activeSelf)
            {
                var c = heldBlock == HomeBlock.Ok ? GhostOk : GhostBad;
                c.a *= 0.7f + 0.3f * (0.5f + 0.5f * Mathf.Sin(t * 5f));
                ghost.color = c;
            }
        }

        // ──────────── 進出 ────────────

        void Enter()
        {
            if (View == null) return;
            Editing = true;
            selected = -1;
            Sfx.Play("ui-open");
            RoomCat.Live?.OnRoomChanged(null);  // 走到一半的貓先坐下（佈置中牠不動，不要原地踏步）
            var tray = UI.ShopRoomTray.Ensure();
            tray.onPick = null;                 // 家裡用「按下」（onPress），點一下也由按下那邊處理
            tray.onPress = OnTrayPress;
            tray.Show(UI.ShopRoomTray.Room.Home);
            UpdateHint();
        }

        void Exit()
        {
            if (holding) CancelHold(false);
            StopShake();
            Editing = false;
            flashUntil = 0f;
            selected = -1;
            ShowGhost(false);
            ShowZones(false, false);
            var tray = UI.ShopRoomTray.Instance;
            if (tray != null)
            {
                if (tray.onPress == (System.Action<string, bool>)OnTrayPress) tray.onPress = null;
                tray.Hide();
            }
            View?.ApplyTint();
            Sfx.Play("ui-close");
        }

        // ──────────── 拿起來 ────────────

        Vector3 MouseWorld()
        {
            if (cam == null) cam = Camera.main;
            var w = cam != null ? cam.ScreenToWorldPoint(Input.mousePosition) : Vector3.zero;
            w.z = 0f;
            return w;
        }

        bool OverTray()
        {
            var tray = UI.ShopRoomTray.Instance;
            return tray != null && tray.PointerOverTray(Input.mousePosition);
        }

        /// <summary>托盤格上按下滑鼠：拿一件出來（還沒擺），按著拖＝拖出來，放開在原格上＝黏在滑鼠上等下一次點。</summary>
        void OnTrayPress(string id, bool isDecor)
        {
            if (!Editing || holding || UIState.ModalOpen) return;
            if (!Furnishings.CanPlaceAtHome(id) || HomeLayout.Unplaced(id) <= 0) { Sfx.Play("deny"); return; }
            var m = MouseWorld();
            var go = FurnishingVisual.Create(id, (Vector2)m, false, transform, FurnitureLight.Mode.NightOnly);
            if (go == null) { Sfx.Play("deny"); return; }

            heldIndex = -1;
            heldId = id;
            heldFlip = origFlip = false;
            heldGo = go;
            grabOffset = new Vector2(0f, -10f);      // 腳在滑鼠下面一點：拿著的時候看得到它站在哪
            heldPos = new Vector2(float.NaN, float.NaN);
            heldByButton = true;
            leftTray = false;
            heldFrame = Time.frameCount;
            others = View.Others(-1);
            BeginHoldCommon();
            Sfx.Play("pickup");
        }

        /// <summary>房間裡按下左鍵：抓起滑鼠底下那件（站著的優先、地毯最後）。點空地＝取消選取。</summary>
        void BeginDragUnderMouse()
        {
            if (OverTray() || UI.CornerHud.BlocksWorldClick(Input.mousePosition)) return;
            StopShake();
            int i = HitTest(MouseWorld());
            if (i < 0)
            {
                if (selected >= 0) { selected = -1; UpdateHint(); }
                return;
            }
            var p = HomeLayout.At(i);
            heldIndex = i;
            heldId = p.id;
            heldFlip = origFlip = p.flip;
            origPos = p.Pos;
            heldGo = View.GoAt(i);
            grabOffset = (Vector2)heldGo.transform.position - (Vector2)MouseWorld();
            heldPos = origPos;
            heldByButton = true;
            leftTray = true;
            heldFrame = Time.frameCount;
            others = View.Others(i);
            selected = i;
            BeginHoldCommon();
            Sfx.Play("pickup");
        }

        void BeginHoldCommon()
        {
            holding = true;
            heldBlock = HomeBlock.Ok;
            heldOverTray = false;
            flashUntil = 0f;
            var art = FurnishingVisual.ArtOf(heldGo);
            if (art != null) art.sortingOrder = OrderHeld;
            ShowZones(true, Furnishings.Flat(heldId));
            if (!float.IsNaN(heldPos.x)) Evaluate();
            MoveHeld();
            UpdateHint();
        }

        /// <summary>滑鼠底下是哪一件（看圖的範圍；疊在一起拿畫在最上面的；地毯最後才試）。</summary>
        int HitTest(Vector3 m)
        {
            int best = -1, bestOrder = int.MinValue;
            bool bestFlat = true;
            for (int i = 0; i < View.Count; i++)
            {
                var art = FurnishingVisual.ArtOf(View.GoAt(i));
                if (art == null || !art.gameObject.activeInHierarchy) continue;
                var b = art.bounds;
                if (!b.Contains(new Vector3(m.x, m.y, b.center.z))) continue;
                bool flat = View.ShapeAt(i).Flat;
                if (best >= 0 && flat && !bestFlat) continue;                    // 站著的優先
                if (best >= 0 && flat == bestFlat && art.sortingOrder <= bestOrder) continue;
                best = i; bestOrder = art.sortingOrder; bestFlat = flat;
            }
            return best;
        }

        // ──────────── 拿著走 ────────────

        void MoveHeld()
        {
            if (heldGo == null) { holding = false; return; }
            bool over = OverTray();
            if (!over) leftTray = true;
            var want = (Vector2)MouseWorld() + grabOffset;
            var snapped = HomePlacement.SnapPos(want);
            heldGo.transform.position = new Vector3(snapped.x, snapped.y, 0f);
            bool moved = snapped != heldPos;
            if (moved) { heldPos = snapped; Evaluate(); }
            if (over != heldOverTray || moved)
            {
                heldOverTray = over;
                ShowGhost(!over);
                TintHeld();
            }
        }

        /// <summary>重算「擺在 heldPos 行不行」、預覽、提示。</summary>
        void Evaluate()
        {
            var s = HomePlacement.Shape(heldId, heldPos, heldFlip);
            var b = HomePlacement.Check(s, others);
            bool changed = b != heldBlock;
            heldBlock = b;
            PlaceGhost(s);
            TintHeld();
            if (changed) UpdateHint();
        }

        void TintHeld()
        {
            var art = FurnishingVisual.ArtOf(heldGo);
            if (art == null) return;
            var c = heldBlock == HomeBlock.Ok ? TintOk : TintBad;
            if (heldOverTray) c.a = 0.55f;             // 拖到托盤上：半透明＝放開就收回
            art.color = c;
        }

        /// <summary>按著拖的那一下放開了。</summary>
        void Release()
        {
            if (OverTray())
            {
                if (heldIndex >= 0) { StoreHeld(); return; }                      // 房間裡的拖回托盤＝收回
                if (!leftTray) { heldByButton = false; heldFrame = Time.frameCount; UpdateHint(); return; }   // 點一下＝黏在滑鼠上
                CancelHold(true);
                return;
            }
            TryDrop();
        }

        void TryDrop()
        {
            if (heldBlock != HomeBlock.Ok)
            {
                if (heldIndex >= 0)
                {
                    // 搬到不行的地方：回原位、抖一下
                    var why = heldBlock;
                    var go = heldGo;
                    CancelHold(false);
                    Deny(go, why);
                }
                else
                {
                    // 從托盤拿的：繼續黏在滑鼠上，讓玩家換個地方
                    heldByButton = false;
                    heldFrame = Time.frameCount;
                    Deny(heldGo, heldBlock);
                }
                return;
            }

            int index;
            if (heldIndex >= 0)
            {
                HomeLayout.Move(heldIndex, heldPos, heldFlip);
                index = heldIndex;
            }
            else
            {
                if (!HomeLayout.Add(heldId, heldPos, heldFlip)) { CancelHold(true); return; }
                index = HomeLayout.Count - 1;
                DestroyTemp();
            }
            EndHoldVisuals();
            holding = false;
            View.Rebuild();
            selected = index;
            Sfx.Play("place");
            UI.ShopRoomTray.Instance?.Refresh();
            UpdateHint();
        }

        /// <summary>房間裡那件拖回托盤上放開：收回。</summary>
        void StoreHeld()
        {
            int i = heldIndex;
            EndHoldVisuals();
            holding = false;
            HomeLayout.RemoveAt(i);
            AfterStore();
        }

        /// <summary>右鍵點房間裡的東西：收回托盤（不退錢）。</summary>
        void StoreUnderMouse()
        {
            if (OverTray() || UI.CornerHud.BlocksWorldClick(Input.mousePosition)) return;
            int i = HitTest(MouseWorld());
            if (i < 0) return;
            StopShake();
            HomeLayout.RemoveAt(i);
            AfterStore();
        }

        void AfterStore()
        {
            selected = -1;
            View.Rebuild();
            Sfx.Play("pickup");
            UI.ShopRoomTray.Instance?.Refresh();
            UpdateHint();
        }

        /// <summary>放回去：搬到一半的回原位、從托盤拿的回托盤。</summary>
        void CancelHold(bool sound)
        {
            if (!holding) return;
            if (heldIndex >= 0 && heldGo != null)
            {
                heldGo.transform.position = new Vector3(origPos.x, origPos.y, 0f);
                if (heldFlip != origFlip) FlipVisual(heldGo);
                var art = FurnishingVisual.ArtOf(heldGo);
                if (art != null)
                {
                    art.sortingOrder = View.OrderAt(heldIndex);
                    art.color = View.BaseTint(heldIndex);
                }
            }
            else DestroyTemp();
            EndHoldVisuals();
            holding = false;
            if (sound) Sfx.Play("pickup");
            UpdateHint();
        }

        void DestroyTemp()
        {
            if (heldIndex < 0 && heldGo != null) { heldGo.SetActive(false); Destroy(heldGo); }
            heldGo = null;
        }

        void EndHoldVisuals()
        {
            ShowGhost(false);
            ShowZones(false, false);
            heldBlock = HomeBlock.Ok;
            heldOverTray = false;
            others = null;
        }

        // ──────────── 翻面 ────────────

        void FlipHeld()
        {
            heldFlip = !heldFlip;
            FlipVisual(heldGo);
            if (!float.IsNaN(heldPos.x)) Evaluate();
            Sfx.Play("ui-click");
        }

        /// <summary>沒拿東西時 F：翻選中的那件（原地翻不下就抖一下）。</summary>
        void FlipSelected()
        {
            var p = HomeLayout.At(selected);
            if (p == null) { selected = -1; UpdateHint(); return; }
            var s = HomePlacement.Shape(p.id, p.Pos, !p.flip);
            var b = HomePlacement.Check(s, View.Others(selected));
            if (b != HomeBlock.Ok) { Deny(View.GoAt(selected), b); return; }
            HomeLayout.Move(selected, p.Pos, !p.flip);
            View.Rebuild();
            Sfx.Play("place");
        }

        /// <summary>左右鏡像一個家具物件（"art" 的 scale.x 取負、光暈的 X 取負）。</summary>
        static void FlipVisual(GameObject go)
        {
            if (go == null) return;
            foreach (Transform c in go.transform)
            {
                if (c.name == "art")
                {
                    var s = c.localScale;
                    c.localScale = new Vector3(-s.x, s.y, s.z);
                }
                else
                {
                    var lp = c.localPosition;
                    c.localPosition = new Vector3(-lp.x, lp.y, lp.z);
                }
            }
        }

        // ──────────── 被擋下來：抖一下＋提示列短暫亮原因 ────────────

        HomeBlock flashBlock;

        void Deny(GameObject go, HomeBlock why)
        {
            Sfx.Play("deny");
            StartShake(go);
            flashBlock = why;
            flashUntil = Time.unscaledTime + FlashSecs;
            UpdateHint();
        }

        void StartShake(GameObject go)
        {
            StopShake();
            if (go == null || (holding && go == heldGo)) return;
            shakeGo = go;
            shakeBase = go.transform.position;
            shakeT0 = Time.unscaledTime;
        }

        /// <summary>
        /// LateUpdate：位置左右晃（越來越小）、圖染紅後褪回原色。
        /// 手上還拿著的那件（從托盤拿、放不下而繼續黏在滑鼠上）不晃 —— 它跟著滑鼠走，紅色由 TintHeld 顯示。
        /// </summary>
        void UpdateShake(float now)
        {
            if (shakeGo == null) return;
            if (!shakeGo.activeInHierarchy || (holding && shakeGo == heldGo)) { shakeGo = null; return; }
            float t = now - shakeT0;
            if (t >= ShakeSecs) { StopShake(); return; }
            float k = 1f - t / ShakeSecs;
            shakeGo.transform.position = shakeBase + new Vector3(Mathf.Sin(t * 70f) * 3f * k, 0f, 0f);
            var art = FurnishingVisual.ArtOf(shakeGo);
            if (art != null) art.color = Color.Lerp(BaseTintOf(shakeGo), new Color(1f, 0.45f, 0.42f), k);
        }

        void StopShake()
        {
            if (shakeGo != null && !(holding && shakeGo == heldGo))
            {
                shakeGo.transform.position = shakeBase;
                var art = FurnishingVisual.ArtOf(shakeGo);
                if (art != null) art.color = BaseTintOf(shakeGo);
            }
            shakeGo = null;
        }

        Color BaseTintOf(GameObject go)
        {
            for (int i = 0; i < View.Count; i++) if (View.GoAt(i) == go) return View.BaseTint(i);
            return Color.white;
        }

        // ──────────── 提示 ────────────

        void UpdateHint()
        {
            var tray = UI.ShopRoomTray.Instance;
            if (tray == null || !Editing) return;
            HomeBlock why = holding ? heldBlock : flashUntil > 0f ? flashBlock : HomeBlock.Ok;
            bool show = why != HomeBlock.Ok;
            Sprite cat = show && why == HomeBlock.CatBed ? RoomCat.IconSprite : null;
            // 剛被擋下來（沒拿東西）也讓原因亮一下：當成「拿著」顯示紅格＋原因
            tray.SetHomeHint(holding || show, selected >= 0, show ? HomePlacement.BlockIcon(why) : null, cat);
        }

        // ──────────── 預覽：腳下的佔地＋不能擺的地方 ────────────

        void ShowGhost(bool on)
        {
            if (ghost != null) ghost.gameObject.SetActive(on && holding);
        }

        void PlaceGhost(in HomeShape s)
        {
            if (ghost == null)
            {
                var go = new GameObject("home-ghost");
                go.transform.SetParent(transform, false);
                ghost = go.AddComponent<SpriteRenderer>();
                ghost.sortingOrder = OrderGhost;
            }
            string key = s.Id + (s.Flip ? ":f" : ":n");
            if (key != ghostKey)
            {
                ghostKey = key;
                if (ghost.sprite != null) { var t = ghost.sprite.texture; Destroy(ghost.sprite); if (t != null) Destroy(t); }
                var rel = new Vector2[s.Foot.Length];
                for (int i = 0; i < rel.Length; i++) rel[i] = s.Foot[i] - s.Pos;
                ghost.sprite = PolySprite(rel);
            }
            ghost.transform.position = new Vector3(s.Pos.x, s.Pos.y, 0f);
            ghost.gameObject.SetActive(holding && !heldOverTray);
        }

        void ShowZones(bool on, bool rugOnly)
        {
            if (on)
            {
                if (zones == null)
                {
                    var go = new GameObject("home-zones");
                    go.transform.SetParent(transform, false);
                    zones = go.AddComponent<SpriteRenderer>();
                    zones.sortingOrder = OrderZones;
                    zones.color = ZoneCol;
                    var o = ZonesOrigin();
                    go.transform.position = new Vector3(o.x, o.y, 0f);
                }
                if (rugOnly) zonesCat ??= ZonesSprite(true);
                else zonesAll ??= ZonesSprite(false);
                zones.sprite = rugOnly ? zonesCat : zonesAll;
            }
            if (zones != null) zones.gameObject.SetActive(on);
        }

        /// <summary>凸多邊形（相對樞紐）→ 1:1 像素的填色貼圖：內側半透明、邊緣 2px 實心。樞紐＝多邊形的原點。</summary>
        static Sprite PolySprite(Vector2[] rel)
        {
            var poly = HomePlacement.Ccw(rel);
            float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
            foreach (var q in poly) { x0 = Mathf.Min(x0, q.x); x1 = Mathf.Max(x1, q.x); y0 = Mathf.Min(y0, q.y); y1 = Mathf.Max(y1, q.y); }
            x0 = Mathf.Floor(x0) - 1f; y0 = Mathf.Floor(y0) - 1f;
            int w = Mathf.CeilToInt(x1 - x0) + 2, h = Mathf.CeilToInt(y1 - y0) + 2;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            var px = new Color32[w * h];
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    float d = HomePlacement.PolyDist(poly, new Vector2(x0 + i + 0.5f, y0 + j + 0.5f));
                    byte a = d > 0f ? (byte)0 : d > -2f ? (byte)255 : (byte)110;
                    px[j * w + i] = new Color32(255, 255, 255, a);
                }
            tex.SetPixels32(px);
            tex.Apply();
            return Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(-x0 / w, -y0 / h), 1f);
        }

        /// <summary>
        /// 不能擺的地方（門→出生點、迎接點、互動點前面、貓窩；rugOnly＝只畫貓窩）→ 一張蓋住整個地板的貼圖（2px 一格，像素風）。
        /// 一次畫成一張，重疊的地方不會疊得更紅。
        /// </summary>
        static Sprite ZonesSprite(bool rugOnly)
        {
            var walk = BrewRoomLayout.Walk;
            float x0 = float.MaxValue, y0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue;
            foreach (var q in walk) { x0 = Mathf.Min(x0, q.x); x1 = Mathf.Max(x1, q.x); y0 = Mathf.Min(y0, q.y); y1 = Mathf.Max(y1, q.y); }
            const float K = 2f;
            int w = Mathf.CeilToInt((x1 - x0) / K) + 1, h = Mathf.CeilToInt((y1 - y0) / K) + 1;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            var px = new Color32[w * h];
            var bed = RoomCat.CatBed;
            var hb = HomePlacement.CatBedHalf;
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    var p = new Vector2(x0 + (i + 0.5f) * K, y0 + (j + 0.5f) * K);
                    // 有號「離邊多遠」：<0 在裡面
                    float best = float.MaxValue;
                    float ex = (p.x - bed.x) / hb.x, ey = (p.y - bed.y) / hb.y;
                    best = Mathf.Min(best, (Mathf.Sqrt(ex * ex + ey * ey) - 1f) * hb.y);
                    if (!rugOnly)
                    {
                        best = Mathf.Min(best, SegDist(p, BrewRoomLayout.ExitAt, BrewRoomLayout.Spawn) - HomePlacement.DoorClear);
                        best = Mathf.Min(best, Vector2.Distance(p, RoomCat.DoorGreet) - HomePlacement.GreetClear);
                        foreach (var u in HomePlacement.UseSpots) best = Mathf.Min(best, Vector2.Distance(p, u) - HomePlacement.UseClear);
                    }
                    byte a = best > 0f ? (byte)0 : best > -K * 1.5f ? (byte)255 : ((i + j) & 3) == 0 ? (byte)150 : (byte)90;   // 邊實心、裡面淡淡的斜點
                    px[j * w + i] = new Color32(255, 255, 255, a);
                }
            tex.SetPixels32(px);
            tex.Apply();
            // 樞紐在左下角 ＝ 地板外接框的左下角（ShowZones 把物件擺在 ZonesOrigin）
            return Sprite.Create(tex, new Rect(0, 0, w, h), Vector2.zero, 1f / K);

            static float SegDist(Vector2 p, Vector2 a, Vector2 b)
            {
                var d = b - a;
                float l2 = d.sqrMagnitude;
                float t = l2 < 1e-6f ? 0f : Mathf.Clamp01(Vector2.Dot(p - a, d) / l2);
                return Vector2.Distance(p, a + d * t);
            }
        }

        /// <summary>地板（可走範圍）外接框的左下角 —— 禁區貼圖的樞紐擺這。</summary>
        static Vector2 ZonesOrigin()
        {
            float x0 = float.MaxValue, y0 = float.MaxValue;
            foreach (var q in BrewRoomLayout.Walk) { x0 = Mathf.Min(x0, q.x); y0 = Mathf.Min(y0, q.y); }
            return new Vector2(x0, y0);
        }
    }
}
