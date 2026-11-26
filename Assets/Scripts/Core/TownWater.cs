using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 城鎮（town）的河：玩家不能直接走過去、要走橋。
    ///
    /// 河是烤進地面圖的（tools/ground/town.py），場景裡沒有任何「河」的物件可以讓 Obstacles 掃到，
    /// 所以改由這裡把離線算好的矩形（<see cref="TownWaterData"/>，tools/gen_town_water.py 產生）
    /// 直接登記成障礙。橋面在遮罩裡本來就不是水（石頭已經扣掉），不用另外挖開。
    ///
    /// ⚠️ 一定要在 <see cref="Obstacles.Begin"/> **之後**呼叫：Begin 會清空所有登記的障礙。
    ///    （PlayerController.Awake 裡緊跟在 Begin 那一行後面。）
    /// ⚠️ 用 AddPoly（凸多邊形）而不是矩形：Obstacles 只有多邊形與橢圓有登記 API，
    ///    矩形的四個頂點就是一個凸多邊形；碰撞時一樣往外長一個玩家半徑（圓角）。
    ///    類別是 "water" —— CarveDoors 只挖 building 類的 Box，不會動到它們；
    ///    編輯器的 SelfCheck 類別統計會出現「water N」。
    /// ⚠️ 只擋玩家：村民（TownFolk）走固定路點、不套碰撞。
    /// </summary>
    public static class TownWater
    {
        public static void Register()
        {
            foreach (var r in TownWaterData.Rects)
            {
                Obstacles.AddPoly("water", new[]
                {
                    new Vector2(r.XMin, r.YMin), new Vector2(r.XMax, r.YMin),
                    new Vector2(r.XMax, r.YMax), new Vector2(r.XMin, r.YMax),
                }, "water");
            }
        }
    }
}
