using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>一天怎麼結束的：自己去睡 / 撐到 02:00 昏倒。給每日結算畫面分辨用。</summary>
    public enum DayEndCause { Sleep, Collapse }

    /// <summary>
    /// 遊戲時間系統 —— 照星露谷的邏輯：
    ///
    /// ● 一天 20 小時：每天 06:00 醒來，不睡覺的話 02:00（隔天）昏倒。玩家可隨時
    ///   Sleep() 提前結束當天。
    /// ● 時間「連續」流動，指針平滑慢慢走（不是每 7.3 秒硬跳一格）。速率同星露谷：
    ///     正常：10 遊戲分鐘 = 7.3 真實秒（1 小時 43.8 秒、一天 20h ≈ 14 分 36 秒）
    ///   文字讀數 ClockText() 才向下取整到 10 分（呈現同星露谷），指針吃連續值平滑轉。
    /// ● 暫停：開選單/對話（UIState.ModalOpen）時傳 paused=true，時間凍結。
    ///
    /// 時間存 static 欄位（換場景保留）＋ 存檔（關遊戲再開接著走）。
    ///
    /// ⚠️ 這是**全遊戲唯一的時間來源**，必須有人每幀呼叫 Tick()。
    ///    在 Unity 這邊由 TimeDriver 負責（原專案是 Clock HUD 順便驅動的，
    ///    那樣時鐘 UI 一旦沒生出來時間就整個停掉 —— 這裡拆開比較安全）。
    /// </summary>
    public static class TimeSystem
    {
        const string Key = "witch.time";

        // 星露谷速率：10 遊戲分鐘 = 7.3 真實秒（正常）/ 9.3833 秒（洞穴減速）
        const float SecPer10MinNormal = 7.3f;
        const float SecPer10MinSlow = 9.3833f;
        const int StepMin = 10;                  // 文字讀數的顯示刻度（10 分鐘）

        const float DayStart = 6 * 60f;          // 360 = 06:00 醒來
        const float DayEnd = 26 * 60f;           // 1560 = 隔天 02:00 昏倒
        const float NightSleep = 20 * 60f;       // 1200 = 白天睡覺會跳到當晚 20:00
        const float Sunset = 18f;                // 18:00 起算夜晚

        static int DaysPerYear => Seasons.DaysPerMonth * Seasons.MonthsPerYear;

        [Serializable] class Save { public int d; public float t; }

        static int totalDays;         // 從開檔起算的第幾天（0 起）
        static float tod = DayStart;  // 一天內的分鐘（連續 float）
        static float sinceSave;       // 距上次存檔的真實秒（節流用）
        static bool slow;
        static bool loaded;
        static readonly List<Action<DayEndCause>> newDayCbs = new();

        static void EnsureLoaded()
        {
            if (loaded) return;
            loaded = true;
            try
            {
                var o = JsonUtility.FromJson<Save>(SaveManager.GetString(Key));
                if (o != null)
                {
                    totalDays = Mathf.Max(0, o.d);
                    tod = Mathf.Clamp(o.t, DayStart, DayEnd);
                    return;
                }
            }
            catch { /* 壞檔 → 重來 */ }
            totalDays = 0; tod = DayStart;
        }

        static void SaveNow() =>
            SaveManager.SetString(Key, JsonUtility.ToJson(new Save { d = totalDays, t = tod }));

        /// <summary>跳到隔天早上 06:00。</summary>
        static void RollToNextDay(DayEndCause cause)
        {
            totalDays += 1;
            tod = DayStart;
            foreach (var cb in newDayCbs.ToArray()) cb(cause);
        }

        /// <summary>目前時刻的「顯示小時」（6..25，其中 24=00:00、25=01:00）。</summary>
        static int DisplayHour() { EnsureLoaded(); return Mathf.FloorToInt(tod / 60f); }

        /// <summary>
        /// 推進時間。dt＝真實秒；paused＝是否凍結（開選單/對話時）。
        /// </summary>
        public static void Tick(float dt, bool paused)
        {
            EnsureLoaded();
            if (paused || !(dt > 0f)) return;
            if (dt > 0.25f) dt = 0.25f;              // 掉幀/剛換場景鉗住
            float per = slow ? SecPer10MinSlow : SecPer10MinNormal;
            tod += dt * (StepMin / per);             // 連續累積遊戲分鐘（平滑）
            if (tod >= DayEnd) RollToNextDay(DayEndCause.Collapse);
            sinceSave += dt;
            if (sinceSave >= 4f) { sinceSave = 0f; SaveNow(); }   // 存檔節流
        }

        /// <summary>
        /// 睡覺：白天睡 → 跳到當晚 20:00；晚上睡 → 跳到隔天 06:00。
        /// 回傳 true 代表跨到了隔天。
        /// </summary>
        public static bool Sleep()
        {
            EnsureLoaded();
            if (IsNight) { RollToNextDay(DayEndCause.Sleep); SaveNow(); return true; }
            tod = NightSleep; SaveNow(); return false;
        }

        public static void SetSlow(bool v) => slow = v;

        /// <summary>註冊「換新的一天」回呼（睡覺或昏倒都會觸發）。</summary>
        public static void OnNewDay(Action<DayEndCause> cb) => newDayCbs.Add(cb);

        /// <summary>從開檔起算的第幾天（1 起）。</summary>
        public static int TotalDay { get { EnsureLoaded(); return totalDays + 1; } }

        public static int Hour => DisplayHour() % 24;
        public static int Minute { get { EnsureLoaded(); return Mathf.FloorToInt(tod % 60f); } }
        public static int Day { get { EnsureLoaded(); return (totalDays % Seasons.DaysPerMonth) + 1; } }
        public static int Month
        {
            get
            {
                EnsureLoaded();
                return (totalDays / Seasons.DaysPerMonth) % Seasons.MonthsPerYear + 1;
            }
        }
        public static int Year { get { EnsureLoaded(); return totalDays / DaysPerYear + 1; } }
        public static int DaysPerMonth => Seasons.DaysPerMonth;

        /// <summary>季節索引 0..3。</summary>
        public static int Season => Seasons.SeasonOfMonth(Month);
        public static SeasonDef SeasonDef => Seasons.All[Season];
        public static string SeasonName => SeasonDef.Name;

        public static string DateText() => $"{Month} 月 {Day} 日";
        public static string DateTextFull() => $"第 {Year} 年 {Month} 月 {Day} 日（{SeasonName}）";

        /// <summary>
        /// 把「從開檔起算的第 N 天」換成日期文字。
        /// 每日結算要顯示「剛結束的那一天」，那時 TotalDay 已經跳到隔天了，所以需要這個。
        /// </summary>
        public static string DateTextOf(int totalDay)
        {
            int n = Mathf.Max(0, totalDay - 1);
            int m = (n / Seasons.DaysPerMonth) % Seasons.MonthsPerYear + 1;
            return $"{m} 月 {n % Seasons.DaysPerMonth + 1} 日";
        }

        /// <summary>今天是節日的話回傳它，否則 null。</summary>
        public static Festival FestivalToday() => Seasons.FestivalOn(Month, Day);

        /// <summary>從某月某日之後算起，一年內的下一個節日（繞過年底；沒有回 null）。</summary>
        public static Festival NextFestivalFrom(int month, int day)
        {
            for (int step = 0; step < DaysPerYear; step++)
            {
                int n = (month - 1) * Seasons.DaysPerMonth + (day - 1) + 1 + step;
                int m = (n / Seasons.DaysPerMonth) % Seasons.MonthsPerYear + 1;
                int d = n % Seasons.DaysPerMonth + 1;
                var f = Seasons.FestivalOn(m, d);
                if (f != null) return f;
            }
            return null;
        }

        /// <summary>這一季的天黑時刻（小時）—— 冬天黑得早、夏天黑得晚。</summary>
        public static float SunsetHour => Sunset + SeasonDef.DuskShift;

        /// <summary>夜晚？（天黑到隔天 02:00）。</summary>
        public static bool IsNight { get { EnsureLoaded(); return tod / 60f >= SunsetHour; } }

        /// <summary>一天過了幾成（0..1，06:00→02:00）。</summary>
        public static float DayProgress { get { EnsureLoaded(); return (tod - DayStart) / (DayEnd - DayStart); } }

        /// <summary>
        /// 連續的「當日時數」，範圍 6.0..26.0。跨午夜仍單調遞增
        /// （24=00:00、25=01:00、26=02:00），適合直接餵天色曲線做插值。
        /// </summary>
        public static float TodHours { get { EnsureLoaded(); return tod / 60f; } }

        public static float HourFraction { get { EnsureLoaded(); return ((DisplayHour() % 12) + (tod % 60f) / 60f) / 12f; } }
        public static float MinuteFraction { get { EnsureLoaded(); return (tod % 60f) / 60f; } }

        /// <summary>"H:MM" 字串，分鐘向下取整到 10（呈現同星露谷；指針本身連續轉）。</summary>
        public static string ClockText()
        {
            EnsureLoaded();
            int h = DisplayHour() % 24;
            int m = Mathf.FloorToInt((tod % 60f) / StepMin) * StepMin;
            return $"{h}:{m:00}";
        }
    }

    /// <summary>
    /// 每幀推進 TimeSystem。
    ///
    /// ⚠️ 原專案是讓時鐘 HUD（Clock.ts）順便驅動時間的 —— 那樣時鐘 UI 一旦沒生出來，
    ///    整個遊戲的時間就停掉（花不長、顧客不來），而且很難查。這裡拆成獨立元件，
    ///    由 PlayerController 喚起，跟 UI 無關。
    /// </summary>
    public class TimeDriver : MonoBehaviour
    {
        public static TimeDriver Instance { get; private set; }

        public static TimeDriver Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("TimeDriver");
            DontDestroyOnLoad(go);
            return go.AddComponent<TimeDriver>();
        }

        void Awake() { Instance = this; }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Update() => TimeSystem.Tick(Time.deltaTime, UIState.ModalOpen);
    }
}
