using UnityEditor;
using UnityEngine;
using WitchShop.Core;

/// <summary>
/// 移植期間的測試工具。空的背包看不出圖示對不對，所以塞一批東西進去。
/// 這幾個指令直接寫存檔（走 SaveManager），Play 起來就看得到。
/// </summary>
public static class DevTools
{
    [MenuItem("Witch Shop/測試用/塞一批道具進背包")]
    public static void FillBag()
    {
        // 每一類都放一點，才驗得到分頁篩選與各自的圖示
        (string name, int qty)[] gifts =
        {
            ("木材", 12), ("樹枝", 8), ("藥草", 5), ("漿果", 7),
            ("金蘋果", 2), ("藍莓", 4),
            ("薰衣草", 3), ("薰衣草種子", 2),
            ("清涼藥水", 2), ("星光藥劑", 1),
            ("焦糖蘋果棒", 3),
        };
        int ok = 0;
        foreach (var g in gifts) if (Inventory.Add(g.name, g.qty)) ok++;
        Debug.Log($"[DevTools] 放進背包 {ok}/{gifts.Length} 種（放不下的是背包種類上限 " +
                  $"{Upgrades.BagSlots()} 擋掉的，那是正常行為）");
    }

    [MenuItem("Witch Shop/測試用/塞一批道具進倉庫")]
    public static void FillStorage()
    {
        (string name, int qty)[] gifts =
        {
            ("黑莓", 20), ("落葉", 15), ("毛地黃", 6), ("星鈴花", 2), ("烈焰藥水", 3),
        };
        foreach (var g in gifts) Storage.Add(g.name, g.qty);
        Debug.Log("[DevTools] 倉庫已塞入 5 種");
    }

    [MenuItem("Witch Shop/測試用/給 5000 金幣")]
    public static void GiveGold()
    {
        Wallet.Add(5000);
        Debug.Log($"[DevTools] 金幣現在是 {Wallet.Gold}");
    }

    /// <summary>
    /// 塞一天的營業紀錄進「今天」—— 進遊戲走到床邊按 E 睡一覺，就看得到滿的每日結算。
    ///
    /// ⚠️ 要塞的是**今天**（DailyLog 的 "t"）不是「昨天」("l")：跨日時 Rollover() 會
    ///    拿今天蓋掉昨天，直接塞 "l" 的話一睡就被歸零的今天洗掉，畫面上全是 0。
    ///
    /// 這裡直接寫 DailyLog 的存檔鍵，DailyLog 沒有對外的寫入 API（它只從遊戲事件記帳）。
    /// 欄位名要跟 DayStats / SaleEntry 一致，改了那邊記得跟著改。
    /// </summary>
    [MenuItem("Witch Shop/測試用/塞一天的營業紀錄（睡一覺看結算）")]
    public static void SeedDay()
    {
        const string key = "witch.daily";
        const string json =
            "{\"t\":{" +
            "\"revenue\":486,\"sales\":7,\"trade\":120,\"spent\":300," +
            "\"gathered\":14,\"brewed\":3,\"rep\":9,\"items\":[" +
            "{\"name\":\"清涼藥水\",\"q\":2,\"g\":168}," +
            "{\"name\":\"藥草\",\"q\":3,\"g\":96}," +
            "{\"name\":\"漿果\",\"q\":1,\"g\":42}," +
            "{\"name\":\"焦糖蘋果棒\",\"q\":1,\"g\":180}]}}";
        SaveManager.SetString(key, json);
        Debug.Log("[DevTools] 已塞入今天的營業紀錄 —— 進遊戲睡一覺就會跳出每日結算");
    }

    [MenuItem("Witch Shop/測試用/清空存檔")]
    public static void Wipe()
    {
        if (!EditorUtility.DisplayDialog("清空存檔",
                $"要刪掉所有存檔嗎？\n\n檔案位置：\n{SaveManager.FilePath}", "刪除", "取消")) return;
        SaveManager.Wipe();
        Debug.Log("[DevTools] 存檔已清空（重開 Unity 讓各模組重新讀取）");
    }

    [MenuItem("Witch Shop/測試用/存檔在哪")]
    public static void ShowSavePath()
    {
        Debug.Log($"[DevTools] 存檔路徑：{SaveManager.FilePath}");
        EditorUtility.RevealInFinder(SaveManager.FilePath);
    }
}
