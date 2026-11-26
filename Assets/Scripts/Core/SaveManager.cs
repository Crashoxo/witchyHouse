using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 中央存檔管理：所有 witch.* 存檔都經過這裡，帶「格式版本號」＋ migration。
    ///
    /// 為什麼要這層：
    ///  1. **版本號**：日後改動任一存檔的資料結構時，舊玩家的存檔不會壞 —— 在
    ///     Migrations 補一條「舊版→新版」的搬移即可，開檔時自動升級。
    ///  2. **單一進出點**：整個遊戲只有這裡真的碰儲存。其他所有模組
    ///     （Wallet/Inventory/…）只認得 GetString/SetString，換後端完全不用動。
    ///
    /// 各模組仍保有自己的「防壞檔驗證」邏輯 —— 這層只負責 read/write 字串與版本，
    /// 不碰各自的資料格式。
    ///
    /// ── 移植註記：後端從 localStorage 換成「一個 JSON 檔」───────────────
    /// Cocos 版用 sys.localStorage，並在註解裡寫明「上 Steam 包 Electron 時只要換掉
    /// backend 這三個方法」。Unity 這邊直接把那一步做掉了：
    ///
    ///   為什麼不用 PlayerPrefs（localStorage 最直接的對應）——
    ///   PlayerPrefs 在 Windows 上是寫**登錄檔**（HKCU\Software\...）。這個遊戲有 16 個
    ///   存檔 key、裡面塞的是整包 JSON 字串，塞進登錄檔又難備份、又難給玩家手動救檔、
    ///   上 Steam 也不能跟雲端存檔對接。
    ///
    ///   所以後端是 Application.persistentDataPath 底下一個 save.json，開機讀進
    ///   Dictionary，寫入時整包存回去。對外 API 跟 Cocos 版一模一樣（字串進、字串出），
    ///   所以 16 個模組一行都不用改。
    /// </summary>
    public static class SaveManager
    {
        /// <summary>存檔格式版本。改變任一 key 的資料結構時 +1，並在 Migrations 補一條升級。</summary>
        public const int SaveVersion = 1;

        /// <summary>版本號自己的存放 key。</summary>
        const string VerKey = "witch.save.version";

        /// <summary>所有已知存檔 key（給版本偵測／清檔用）。**新增存檔 key 時記得補進這裡。**</summary>
        public static readonly string[] SaveKeys =
        {
            "witch.gold",            // Wallet：金幣
            "witch.stock",           // Inventory：背包堆疊
            "witch.shop.listings",   // ShopStock：貨架上架
            "witch.time",            // TimeSystem：日期/時刻
            "witch.quests.state",    // Quests：已接/已領
            "witch.quests.counters", // Quests：目標累計計數
            "witch.upgrades",        // Upgrades：升級等級
            "witch.decor.owned",     // DecorCatalog：擁有的裝飾
            "witch.decor.placed",    // DecorCatalog：擺出的裝飾
            "witch.daily",           // DailyLog：當日統計＋前一天結算
            "witch.reputation",      // Reputation：名聲點數
            "witch.friendship",      // Friendship：村民友誼度
            "witch.garden",          // Garden：後花園每一格種了什麼、澆水時間
            "witch.storage",         // Storage：房間倉庫的存貨
            "witch.outfit",          // Outfits：現在穿哪一套造型
            "witch.room",            // RoomLayout：店裡的家具擺在哪幾格
            "witch.shop.display",    // ShopDisplay：上架商品玩家指定的陳列位置（家具 uid＋位子）
            "witch.tips.shopedit",   // ShopRoomEditor：第一次進店的「按 R 佈置」提示跳過了沒
            "witch.shop.sign",       // ShopSign：門口招牌開店／關店（"1"/"0"；沒有＝開店）
        };
        // ⚠️ "witch.audio"（Sfx：音效音量／音樂音量／靜音）**刻意不列在這裡**：那是玩家的偏好、不是遊戲進度，
        //    開新遊戲（Wipe）不該把音量重設；它也不該被當成「這是舊存檔」的判斷依據。

        // ──────────── 後端：整個遊戲唯一真正碰儲存的地方 ────────────

        static string SavePath => Path.Combine(Application.persistentDataPath, "save.json");

        static Dictionary<string, string> data;
        static bool loaded;

        /// <summary>存檔檔案的內容形狀（JsonUtility 不吃 Dictionary，所以用兩個平行陣列）。</summary>
        [Serializable]
        class SaveFile
        {
            public List<string> keys = new();
            public List<string> values = new();
        }

        static void EnsureLoaded()
        {
            if (loaded) return;
            loaded = true;
            data = new Dictionary<string, string>();
            try
            {
                if (File.Exists(SavePath))
                {
                    var f = JsonUtility.FromJson<SaveFile>(File.ReadAllText(SavePath));
                    if (f?.keys != null && f.values != null)
                        for (int i = 0; i < f.keys.Count && i < f.values.Count; i++)
                            data[f.keys[i]] = f.values[i];
                }
            }
            catch (Exception e)
            {
                // 壞檔就當全新遊戲 —— 不要因為存檔壞掉就整個開不起來
                Debug.LogWarning($"[SaveManager] 讀檔失敗，當作新遊戲：{e.Message}");
                data = new Dictionary<string, string>();
            }
            Migrate();
        }

        static void Flush()
        {
            try
            {
                var f = new SaveFile();
                foreach (var kv in data) { f.keys.Add(kv.Key); f.values.Add(kv.Value); }
                File.WriteAllText(SavePath, JsonUtility.ToJson(f));
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[SaveManager] 寫檔失敗：{e.Message}");
            }
        }

        // ──────────── 版本與 migration ────────────

        /// <summary>
        /// 版本升級表：key＝來源版本 v，值＝把「v 版的存檔」就地改寫成「v+1 版」。
        /// v0（沒有版本號的舊存檔）→ v1：現行格式即 v1 基準，不需搬資料。
        /// 之後例如把某 key 換結構時：Migrations[1] = () =&gt; { ...讀舊寫新... } 並把 SaveVersion 改 2。
        /// </summary>
        static readonly Dictionary<int, Action> Migrations = new()
        {
            [0] = () => { /* v0 → v1：現行格式就是 v1 基準，無需轉換 */ },
        };

        /// <summary>讀目前存檔的版本；沒有版本號時：已有任何存檔＝舊檔(v0)，全新遊戲＝視為最新版。</summary>
        static int ReadVersion()
        {
            if (data.TryGetValue(VerKey, out var raw) && int.TryParse(raw, out var n)) return n;
            foreach (var k in SaveKeys) if (data.ContainsKey(k)) return 0;   // 升級前的舊存檔
            return SaveVersion;                                             // 全新遊戲
        }

        /// <summary>逐版套用 migration，最後把版本號蓋成最新。</summary>
        static void Migrate()
        {
            int v = ReadVersion();
            while (v < SaveVersion)
            {
                if (Migrations.TryGetValue(v, out var step))
                {
                    try { step(); }
                    catch (Exception e) { Debug.LogWarning($"[SaveManager] migration {v} 失敗：{e.Message}"); }
                }
                v++;
            }
            data[VerKey] = SaveVersion.ToString();
            Flush();
        }

        // ──────────── 對外 API（跟 Cocos 版一致）────────────

        /// <summary>目前存檔格式版本。</summary>
        public static int Version => SaveVersion;

        /// <summary>讀原始字串（無值回 null）—— 各模組沿用自己的解析/驗證。</summary>
        public static string GetString(string key)
        {
            EnsureLoaded();
            return data.TryGetValue(key, out var v) ? v : null;
        }

        /// <summary>寫原始字串。</summary>
        public static void SetString(string key, string val)
        {
            EnsureLoaded();
            data[key] = val;
            Flush();
        }

        /// <summary>刪一個 key。</summary>
        public static void Remove(string key)
        {
            EnsureLoaded();
            if (data.Remove(key)) Flush();
        }

        /// <summary>清掉所有存檔（開新遊戲用），並把版本號設為最新。</summary>
        public static void Wipe()
        {
            EnsureLoaded();
            foreach (var k in SaveKeys) data.Remove(k);
            data[VerKey] = SaveVersion.ToString();
            Flush();
        }

        /// <summary>存檔檔案在哪（給玩家手動備份／回報問題時用）。</summary>
        public static string FilePath => SavePath;
    }
}
