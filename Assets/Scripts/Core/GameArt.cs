using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>村民走路表的列（＝面向）。</summary>
    public static class VillagerDir { public const int Down = 0, Side = 1, Up = 2; }

    /// <summary>
    /// 方向索引：0 南（下）起、每 45° 逆時針一格。
    /// 對應圖集的欄：south, south-east, east, north-east, north, north-west, west, south-west。
    /// </summary>
    public static class WitchDir { public const int South = 0, East = 2, North = 4, West = 6; }

    /// <summary>
    /// 遊戲美術的執行期載入器：把 Assets/Resources/ 底下的圖依路徑載進 Dictionary，
    /// 供背包圖示、貨架、顧客、UI 共用。
    ///
    /// ── 跟 Cocos 版的差別 ────────────────────────────────────────────
    /// 原本 Cocos 的 resources.load 是**非同步**的，所以 GameArt.ts 有一整套
    /// pending / jobDone() / onReady() 的計數與回呼機制，還要用 w8Seq 擋掉
    /// 「換裝的回呼晚於預載的回呼、把新造型蓋回舊的」這種競態。
    ///
    /// Unity 的 Resources.Load 是**同步**的 —— 上面那些全部不需要了，連同競態一起消失。
    /// 但 Ready / OnReady() 這兩個對外 API 特意保留（Ready 恆為已載入、OnReady 立刻執行），
    /// 這樣其他檔的呼叫端一行都不用改。
    ///
    /// ⚠️ 代價是切場景時會同步卡一下。目前 17MB 圖、又有分區載入，應該可接受；
    ///    真的卡了再換 Resources.LoadAsync + 協程，對外 API 不用動。
    /// </summary>
    public static class GameArt
    {
        // ──────────── 走圖排法（跟原專案一致）────────────

        /// <summary>村民走圖：4 欄（動畫幀）× 3 列（下／側／上）。單格大小由圖檔尺寸算出。</summary>
        const int VillagerCols = 4, VillagerRows = 3;

        static readonly string[] VillagerFiles =
        {
            "frog", "fox", "rabbit", "hedgehog", "witch",
            "deer", "broomwitch", "fairy", "traveler", "mage", "rabbitwitch",
        };

        /// <summary>表情動畫：檔名 → (單幀寬, 單幀高, 幀數)（橫向 strip）。</summary>
        static readonly Dictionary<string, (int W, int H, int N)> EmoteInfo = new()
        {
            ["emo18"] = (33, 30, 28), ["emo3"] = (29, 26, 29), ["emo2"] = (43, 30, 29),
            ["emo32"] = (57, 48, 28), ["emo51"] = (29, 55, 28),
        };

        static readonly string[] PortraitFiles =
        {
            "gnome", "witch", "elf", "forestboy", "badger", "fox",
            "hedgehog", "rabbit", "bear", "squirrel", "wolf", "mouse",
        };

        static readonly string[] DecorFiles =
        {
            "succulent", "daisypot", "violetpot", "birdcage_small", "bonsai",
            "ivy_hanging", "roses_vase", "lily_vase", "sunflower_vase", "autumn_vase",
            "potted_fern", "window_box", "birdcage_large", "blue_urn",
            "wildflower_basket", "flower_case",
            "herb_shelf", "crystal_shelf", "potion_shelf",
        };

        /// <summary>時鐘盤面零件（Resources/ui/clock 底下）：盤面／日月圖示／指針。</summary>
        static readonly string[] ClockFiles = { "face", "sun", "moon", "hand-hour", "hand-min", "hand-day" };

        /// <summary>季節圖標，索引＝TimeSystem.Season（0 春 … 3 冬）。</summary>
        static readonly string[] SeasonFiles = { "spring", "summer", "autumn", "winter" };

        const int CauldronFrameCount = 6;   // Resources/cauldron/f0..f5
        const int GatherFrameCount = 3;     // witch/gather1..3：彎腰伸手→捏起→起身舉起
        const int WaterFrameCount = 4;
        const int PickFrameCount = 4;

        static readonly string[] SoilFiles = { "soil-dry", "soil-wet" };

        /// <summary>花的走圖：6 欄（成長階段）× 2 列（第 0 列健康、第 1 列枯萎）。</summary>
        const int FlowerCols = 6, FlowerRows = 2;

        // ──────────── 女巫圖集（witch8）────────────
        //
        // Resources/witch8/<造型>.png 的排法（由原專案 tools/export_witch8.py 產生）：
        //   列 0       站姿，欄＝方向
        //   列 1..8    走路，列 1+d ＝方向 d，欄＝動畫幀
        //   列 9..16   跑步，列 9+d ＝方向 d，欄＝動畫幀
        //   列 17..24  施法，列 17+d ＝方向 d，欄＝動畫幀（6 幀）
        //
        // ⚠️ 施法那組是所有「動作」共用的：施法、澆水、採集、摘花、種花。
        //    新角色沒有蹲下的圖，所以圖集裡不再有前一位紫袍女巫的任何一格。
        //    之後真的做了蹲下的八方向圖，再加一段列並讓 gather/pick 改讀那組即可。

        const int W8Cols = 8, W8Rows = 25;
        const int W8RowWalk = 1, W8RowRun = 9, W8RowCast = 17;
        const int W8CastFrames = 6;

        public const int WitchDirs = 8;

        /// <summary>
        /// 女巫節點的縮放。**照星露谷的人物比例定** —— 星露谷 1280×720 一格 64px，
        /// 農夫可見身高約 112px ＝畫面高的 15.5%；我們的設計解析度是 960×640，
        /// 所以要 640×0.155 ≈ 99px，66 × 1.6 = 106（可見 93px，14.5%）剛好落在那個帶上。
        /// 1:1 畫的話只有畫面高的 10%，比星露谷小了一號。
        /// 村民要一起改（見 VillagerAnim.Scale），不然大人會比女巫矮。
        /// </summary>
        public const float WitchScale = 1.6f;

        // ──────────── 快取 ────────────

        static readonly Dictionary<string, Sprite> items = new();         // 材料/藥水名 → 圖
        static readonly Dictionary<string, Sprite[][]> villagers = new(); // 村民名 → [面向][幀]
        static readonly Dictionary<string, Sprite[]> emotes = new();      // 表情名 → 動畫幀
        static readonly Dictionary<string, Sprite> portraits = new();
        static readonly Dictionary<string, Sprite> decor = new();
        static readonly Dictionary<string, Sprite> clockParts = new();
        static readonly Dictionary<string, Sprite> seasonIcons = new();
        static readonly Dictionary<string, Sprite> soil = new();
        static readonly Dictionary<string, Sprite[][]> flowers = new();   // 花名 → [健康/枯萎][階段]
        static readonly Dictionary<string, Sprite> candyArt = new();
        static readonly Dictionary<string, Sprite> furnitureArt = new();

        static readonly Sprite[] cauldron = new Sprite[CauldronFrameCount];
        static readonly Sprite[] gather = new Sprite[GatherFrameCount];
        static readonly Sprite[] water = new Sprite[WaterFrameCount];
        static readonly Sprite[] pick = new Sprite[PickFrameCount];

        static Sprite[] w8Idle = Array.Empty<Sprite>();
        static Sprite[][] w8Walk = Array.Empty<Sprite[]>();
        static Sprite[][] w8Run = Array.Empty<Sprite[]>();
        static Sprite[][] w8Cast = Array.Empty<Sprite[]>();
        static Sprite w8Sleep;

        static Sprite castFrame, sleepingFrame;          // 舊手繪女巫的墊底圖
        static Sprite dialogueBoxFrame, questScrollFrame, updateFrameArt;
        static Sprite brewRoomDayFrame, brewRoomNightFrame, gardenFrame, shopRoomFrame;

        static string outfitId = "";                     // ""＝預設造型
        static readonly HashSet<string> requested = new();
        static bool started;

        // ──────────── 載入工具 ────────────

        static Texture2D Tex(string path)
        {
            var t = Resources.Load<Texture2D>(path);
            if (t == null) Debug.LogWarning($"[GameArt] 載入失敗 {path}");
            return t;
        }

        static void LoadImg(Dictionary<string, Sprite> map, string key, string path)
        {
            var t = Tex(path);
            if (t != null) map[key] = SheetSlicer.Whole(t);
        }

        static Sprite LoadSingle(string path, Vector2? pivot = null)
        {
            var t = Tex(path);
            return t != null ? SheetSlicer.Whole(t, pivot) : null;
        }

        static void LoadIndexed(Sprite[] arr, int i, string path, Vector2? pivot = null)
        {
            var t = Tex(path);
            if (t != null) arr[i] = SheetSlicer.Whole(t, pivot);
        }

        /// <summary>載入表情 strip，切成每幀一個 Sprite。</summary>
        static void LoadEmote(string name)
        {
            var info = EmoteInfo[name];
            var t = Tex($"emotes/{name}");
            if (t == null) return;
            var arr = new Sprite[info.N];
            for (int i = 0; i < info.N; i++) arr[i] = SheetSlicer.StripCell(t, i, info.W, info.H);
            emotes[name] = arr;
        }

        /// <summary>
        /// 載入女巫圖集，依 W8_* 的排法切成站姿/走路/跑步/施法。
        /// </summary>
        /// <param name="id">造型 id（""＝預設那張 base.png）</param>
        static void LoadWitch8(string id)
        {
            string file = string.IsNullOrEmpty(id) ? "base" : id;
            var t = Tex($"witch8/{file}");
            if (t != null)
            {
                var idle = new Sprite[WitchDirs];
                var walk = new Sprite[WitchDirs][];
                var run = new Sprite[WitchDirs][];
                var cast = new Sprite[WitchDirs][];
                for (int d = 0; d < WitchDirs; d++)
                {
                    // ⚠️ 樞紐一律用 SheetSlicer.Foot（格子底邊）—— 女巫的 SpriteRenderer
                    //    就掛在 Player 本身，沒有「圖往上推半身高」的子物件，所以要靠樞紐
                    //    讓 position ＝ 落腳點，才跟村民/家具/搬過來的座標同一套。
                    idle[d] = SheetSlicer.Cell(t, d, 0, W8Cols, W8Rows, SheetSlicer.Foot);
                    walk[d] = SheetSlicer.Row(t, W8RowWalk + d, W8Cols, W8Rows, SheetSlicer.Foot);
                    run[d] = SheetSlicer.Row(t, W8RowRun + d, W8Cols, W8Rows, SheetSlicer.Foot);
                    var ca = new Sprite[W8CastFrames];
                    for (int c = 0; c < W8CastFrames; c++)
                        ca[c] = SheetSlicer.Cell(t, c, W8RowCast + d, W8Cols, W8Rows, SheetSlicer.Foot);
                    cast[d] = ca;
                }
                w8Idle = idle; w8Walk = walk; w8Run = run; w8Cast = cast;
            }
            // 睡覺立繪是另一張（含床，裁切框跟角色不一樣）
            w8Sleep = LoadSingle(string.IsNullOrEmpty(id) ? "witch8/sleep" : $"witch8/{id}-sleep");
        }

        /// <summary>載入一位村民的走路表，切成 [列][欄]（列＝面向，欄＝動畫幀）。</summary>
        static void LoadVillager(string name)
        {
            var t = Tex($"villagers/{name}");
            if (t == null) return;
            var rows = new Sprite[VillagerRows][];
            for (int r = 0; r < VillagerRows; r++)
                rows[r] = SheetSlicer.Row(t, r, VillagerCols, VillagerRows);
            villagers[name] = rows;
        }

        /// <summary>
        /// 載入一種花的走圖，切成 [列][階段]（列 0 健康、列 1 枯萎）。
        /// 順便把「開花那一格」登記成該花的道具圖示，背包/貨架/顧客就都有圖可用。
        /// </summary>
        static void LoadFlower(string art, string flowerName)
        {
            var t = Tex($"garden/{art}");
            if (t == null) return;
            var rows = new Sprite[FlowerRows][];
            for (int r = 0; r < FlowerRows; r++)
                rows[r] = SheetSlicer.Row(t, r, FlowerCols, FlowerRows);
            flowers[art] = rows;
            items[flowerName] = rows[0][FlowerCols - 2];   // 盛開那一格＝道具圖示
        }

        // ──────────── 分區載入 ────────────

        /// <summary>場景名 → 除了 common 之外還要載入的區域組。</summary>
        static readonly Dictionary<string, string[]> SceneGroups = new()
        {
            ["main"] = Array.Empty<string>(),                          // 森林：只需 common
            ["town"] = new[] { "portraits", "decor", "villagers" },     // 城鎮
            ["shop"] = new[] { "shop", "decor", "villagers" },          // 自己的店
            ["brew"] = new[] { "brew" },                                // 藥水室
            ["garden"] = new[] { "garden", "villagers" },               // 後花園
            ["candy"] = new[] { "candy" },                              // 糖果鎮
        };

        /// <summary>保險用：全部區域組（拿不到場景名時退回全載）。</summary>
        static readonly string[] AllAreaGroups =
            { "portraits", "decor", "shop", "villagers", "garden", "brew", "candy" };

        /// <summary>載入一個區域組（idempotent —— 已請求過就跳過）。</summary>
        static void LoadGroup(string name)
        {
            if (!requested.Add(name)) return;

            switch (name)
            {
                case "common":
                    foreach (var kv in Items.ItemFiles) LoadImg(items, kv.Key, $"items/{kv.Value}");
                    foreach (var kv in Items.PotionItems) LoadImg(items, kv.Key, $"potions/{kv.Value}");
                    // 糖果鎮進的貨也要在背包/貨架/顧客那邊看得到圖 → 放 common
                    foreach (var kv in Items.CandyItems) LoadImg(items, kv.Key, $"candy/{kv.Value}");
                    foreach (var f in ClockFiles) LoadImg(clockParts, f, $"ui/clock/{f}");
                    foreach (var f in SeasonFiles) LoadImg(seasonIcons, f, $"ui/season/{f}");
                    dialogueBoxFrame = LoadSingle("ui/dialogue-box");
                    questScrollFrame = LoadSingle("ui/quest-scroll");
                    updateFrameArt = LoadSingle("ui/update-frame");
                    LoadWitch8(outfitId);
                    // 舊手繪女巫的施法/睡覺姿勢：只在圖集載不到時墊底
                    // 這幾張也是直接貼到 Player 的 SpriteRenderer 上 → 跟圖集一樣要腳底樞紐，
                    // 不然墊底的時候女巫會整個往上跳半身高。
                    // （sleepingFrame 例外：那是 SleepOverlay 的立繪，不掛在 Player 上）
                    castFrame = LoadSingle("witch/cast", SheetSlicer.Foot);
                    sleepingFrame = LoadSingle("witch/sleeping");
                    for (int i = 0; i < GatherFrameCount; i++)
                        LoadIndexed(gather, i, $"witch/gather{i + 1}", SheetSlicer.Foot);
                    // 花與種子的圖示要在每個場景都拿得到（背包、貨架、顧客想要的東西都會用到），
                    // 所以放 common；只有後花園會用到的土壤磚與澆水姿勢才留在 garden 組。
                    foreach (var f in GardenData.Flowers)
                    {
                        LoadFlower(f.Art, f.Flower);
                        LoadImg(items, f.Seed, $"garden/{f.Art}-seed");
                    }
                    break;

                case "portraits":
                    foreach (var f in PortraitFiles) LoadImg(portraits, f, $"portraits/{f}");
                    break;

                case "decor":
                    foreach (var f in DecorFiles) LoadImg(decor, f, $"decor/{f}");
                    // 家具跟裝飾同一組：花店（城鎮）要畫得出家具圖示，店裡要擺出來，兩邊都載得到
                    foreach (var f in Furniture.All) LoadImg(furnitureArt, f.Id, $"furniture/{f.Id}");
                    break;

                case "shop":
                    foreach (var k in EmoteInfo.Keys) LoadEmote(k);
                    shopRoomFrame = LoadSingle("rooms/shop-room");
                    break;

                case "villagers":
                    foreach (var f in VillagerFiles) LoadVillager(f);
                    break;

                case "garden":
                    foreach (var f in SoilFiles) LoadImg(soil, f, $"garden/{f}");
                    // 同上：貼到 Player 上的動作圖 → 腳底樞紐
                    for (int i = 0; i < WaterFrameCount; i++)
                        LoadIndexed(water, i, $"witch/water{i + 1}", SheetSlicer.Foot);
                    for (int i = 0; i < PickFrameCount; i++)
                        LoadIndexed(pick, i, $"witch/pick{i + 1}", SheetSlicer.Foot);
                    gardenFrame = LoadSingle("rooms/garden");
                    break;

                case "candy":
                    // ⚠️ 地圖與房子/裝飾在 Cocos 版是場景節點（圖在 assets/art/candy，場景用 uuid 參照），
                    //    所以原本這裡不載。Unity 這邊 art/ 也搬進了 Resources，之後 CandyTown 可以直接載；
                    //    先維持原行為，只載執行期才生成的 NPC 與路人。
                    foreach (var c in Candy.Critters) LoadImg(candyArt, c.Art, $"candy/{c.Art}");
                    break;

                case "brew":
                    for (int i = 0; i < CauldronFrameCount; i++) LoadIndexed(cauldron, i, $"cauldron/f{i}");
                    brewRoomDayFrame = LoadSingle("rooms/brew-room-day");
                    brewRoomNightFrame = LoadSingle("rooms/brew-room-night");
                    // 造型立繪只有房間裡的衣櫃會用到，所以掛在 brew 組，不佔 common
                    // （資料表叫 OutfitCatalog 而不是 Outfits —— Core 命名空間裡有一個
                    //   同名的 Outfits 管「現在穿哪一套」，撞名時錯誤訊息完全看不出原因）
                    foreach (var o in OutfitCatalog.All)
                        if (!string.IsNullOrEmpty(o.Portrait))
                            LoadImg(portraits, o.Portrait, $"portraits/{o.Portrait}");
                    break;
            }
        }

        // ──────────── 對外 API（跟 Cocos 版一致，呼叫端不用改）────────────

        /// <summary>
        /// 目前已請求的所有組是否都載入完成。
        /// Unity 的 Resources.Load 是同步的，所以 Preload() 一回來就是好了。
        /// </summary>
        public static bool Ready => started;

        /// <summary>
        /// 開始預載（重複呼叫安全）。載入 common ＋該場景的區域組。
        /// 換場景後各元件於 Awake 再呼叫一次，就會補載新場景需要的組。
        /// ⚠️ 未知場景 → 退回全部載入（等同原專案行為，寧可不省也不缺圖）。
        /// </summary>
        public static void Preload(string sceneName = null)
        {
            started = true;
            LoadGroup("common");
            sceneName ??= SceneManager.GetActiveScene().name;
            var groups = SceneGroups.TryGetValue(sceneName, out var g) ? g : AllAreaGroups;
            foreach (var n in groups) LoadGroup(n);
        }

        /// <summary>載入完成的回呼。同步載入下就是立刻執行（API 保留，呼叫端不用改）。</summary>
        public static void OnReady(Action cb)
        {
            if (!started) Preload();
            cb?.Invoke();
        }

        /// <summary>
        /// 換上某套造型的圖：id ＝ Resources/witch8/&lt;id&gt;.png，空字串＝回到預設那批。
        /// 同步載入，所以沒有 Cocos 版那個「晚到的回呼蓋掉新造型」的競態要擋。
        /// </summary>
        public static void ApplyOutfit(string id)
        {
            if (id == outfitId) return;
            outfitId = id;
            started = true;
            LoadWitch8(id);          // 造型＝同一張圖集的改色版，整張換掉
        }

        /// <summary>女巫圖集載好了沒（沒好的話 CharacterAnimator 會先用場景指定的舊圖）。</summary>
        public static bool WitchReady() => w8Idle.Length > 0;

        static int WrapDir(int dir) => ((dir % WitchDirs) + WitchDirs) % WitchDirs;

        /// <summary>某個方向的站姿（dir 見 WitchDir；未載入回 null）。</summary>
        public static Sprite WitchIdle(int dir) =>
            w8Idle.Length > 0 ? w8Idle[WrapDir(dir)] : null;

        /// <summary>某個方向的走路幀（未載入回空陣列）。</summary>
        public static Sprite[] WitchWalk(int dir) =>
            w8Walk.Length > 0 ? w8Walk[WrapDir(dir)] : Array.Empty<Sprite>();

        /// <summary>某個方向的跑步幀（衝刺用；未載入回空陣列 → 呼叫端自己退回走路）。</summary>
        public static Sprite[] WitchRun(int dir) =>
            w8Run.Length > 0 ? w8Run[WrapDir(dir)] : Array.Empty<Sprite>();

        /// <summary>
        /// 某個方向的動作動畫幀（8 方向各 6 幀）。
        /// **施法／澆水／採集／摘花／種花共用**這一組 —— 新角色只做了這一段動作動畫。
        /// </summary>
        public static Sprite[] ActionFrames(int dir = WitchDir.South) =>
            w8Cast.Length > 0 ? w8Cast[WrapDir(dir)] : Array.Empty<Sprite>();

        /// <summary>某個方向的施法幀（沒有圖集時退回舊的單張姿勢）。</summary>
        public static Sprite[] CastFrames(int dir = WitchDir.South)
        {
            var v = ActionFrames(dir);
            if (v.Length > 0) return v;
            return castFrame != null ? new[] { castFrame } : Array.Empty<Sprite>();
        }

        static Sprite[] ActionOrLegacy(int dir, Sprite[] legacy)
        {
            var v = ActionFrames(dir);
            return v.Length > 0 ? v : legacy;
        }

        public static Sprite[] GatherFrames(int dir = WitchDir.South) => ActionOrLegacy(dir, gather);
        public static Sprite[] WaterFrames(int dir = WitchDir.South) => ActionOrLegacy(dir, water);
        public static Sprite[] PickFrames(int dir = WitchDir.South) => ActionOrLegacy(dir, pick);

        /// <summary>已載入的村民名字（TownFolk / CustomerManager 從這裡挑人）。</summary>
        public static string[] VillagerNames()
        {
            var outList = new List<string>(villagers.Count);
            foreach (var kv in villagers) outList.Add(kv.Key);
            return outList.ToArray();
        }

        /// <summary>某位村民某個面向的走路幀（面向見 VillagerDir）。</summary>
        public static Sprite[] VillagerFrames(string name, int dir) =>
            villagers.TryGetValue(name, out var rows) && dir >= 0 && dir < rows.Length
                ? rows[dir] : Array.Empty<Sprite>();

        public static Sprite Item(string name) => items.GetValueOrDefault(name);
        public static Sprite Portrait(string name) => portraits.GetValueOrDefault(name);
        public static Sprite Decoration(string id) => decor.GetValueOrDefault(id);
        public static Sprite FurnitureArt(string id) => furnitureArt.GetValueOrDefault(id);
        public static Sprite CandyArt(string art) => candyArt.GetValueOrDefault(art);
        public static Sprite ClockPart(string name) => clockParts.GetValueOrDefault(name);
        public static Sprite[] Emote(string name) => emotes.GetValueOrDefault(name, Array.Empty<Sprite>());
        public static Sprite[] CauldronFrames() => cauldron;

        /// <summary>季節圖標（0 春 … 3 冬）。</summary>
        public static Sprite SeasonIcon(int season) =>
            season >= 0 && season < SeasonFiles.Length
                ? seasonIcons.GetValueOrDefault(SeasonFiles[season]) : null;

        /// <summary>土壤磚（乾/濕）。</summary>
        public static Sprite Soil(bool wet) => soil.GetValueOrDefault(wet ? "soil-wet" : "soil-dry");

        /// <summary>某種花在某個階段的圖（wilting＝走枯萎那一列）。</summary>
        public static Sprite Flower(string art, int stage, bool wilting)
        {
            if (!flowers.TryGetValue(art, out var rows)) return null;
            var row = rows[wilting ? 1 : 0];
            return stage >= 0 && stage < row.Length ? row[stage] : null;
        }

        public static Sprite WitchSleep => w8Sleep != null ? w8Sleep : sleepingFrame;
        public static Sprite DialogueBox => dialogueBoxFrame;
        public static Sprite QuestScroll => questScrollFrame;
        public static Sprite UpdateFrame => updateFrameArt;
        public static Sprite ShopRoom => shopRoomFrame;
        public static Sprite GardenRoom => gardenFrame;
        public static Sprite BrewRoom(bool night) => night ? brewRoomNightFrame : brewRoomDayFrame;
    }
}
