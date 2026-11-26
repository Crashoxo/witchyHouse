using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace WitchShop.Core
{
    /// <summary>
    /// 背景音樂：依「現在在哪個場景＋是不是晚上」自己挑曲、交叉淡變，呼叫端什麼都不用做。
    ///
    /// ── 選曲規則（改這裡：<see cref="Choose"/>）──────────────────
    ///   main（森林）、town（城鎮）  白天 day、晚上 night
    ///   candy（糖果鎮）            白天 candy、晚上 night
    ///   shop、brew、garden（室內）  shop（不分日夜）
    ///   其他場景                   不播（淡出）
    /// 換場景時（<c>SceneManager.sceneLoaded</c>）重選一次；日夜交替在 Update 裡看
    /// <see cref="TimeSystem.IsNight"/>，**狀態變了才重選**。
    /// ⚠️ 要換的曲子跟現在播的一樣就**完全不動** —— 森林走到城鎮、店裡進藥水室，音樂不會斷、不會從頭來。
    ///
    /// ── 音量 ────────────────────────────────────────────────
    /// 音量 ＝ <see cref="Sfx.MusicVolume"/> × 交叉淡變係數；<see cref="Sfx.Muted"/> 時壓到 0
    /// （照樣在播，解除靜音就接著響）。設定都存在 Sfx 那邊，這裡訂閱 <see cref="Sfx.Changed"/> 即時反映。
    /// 兩個 AudioSource 輪流當「新的那首」，約 1.2 秒交叉淡變，用 <c>Time.unscaledDeltaTime</c>（不受暫停影響）。
    ///
    /// ── 音檔 ────────────────────────────────────────────────
    /// <c>Resources/audio/bgm/&lt;名字&gt;.wav</c>，照檔名載入、載過就快取。現在那四首是
    /// <c>tools/gen_bgm.py</c> 合成的 8-bit 佔位曲（無縫循環）；有正式音樂時**用同名檔蓋掉就好**，程式不用改
    /// （副檔名可以換 .ogg，但同名的舊 .wav 要刪掉）。匯入設定由 <c>Editor/BgmImporter.cs</c> 套成 Vorbis。
    /// 正式音樂要自己做好循環點（頭尾接得起來），這裡是整首 loop 播。
    ///
    /// ⚠️ 找不到檔案時**靜默略過**（同一個名字只警告一次），絕不丟例外 —— 跟 Sfx 同一個原則。
    /// ⚠️ **不另外掛 AudioListener**：Sfx 的常駐物件已經有一個（見 Sfx 的註解）。
    /// ⚠️ 網頁版（WebGL）瀏覽器要等玩家第一次點擊／按鍵之後才准出聲 —— 開場那幾秒沒有音樂是正常的，
    ///    之後會從當下的位置接著響。
    /// </summary>
    public class Bgm : MonoBehaviour
    {
        /// <summary>音檔在 Resources 底下的資料夾（小寫，見 PortNotes）。</summary>
        const string Folder = "audio/bgm/";
        /// <summary>交叉淡變的長度（秒，真實時間）。</summary>
        const float FadeTime = 1.2f;

        static Bgm instance;
        static readonly Dictionary<string, AudioClip> clips = new();
        static readonly HashSet<string> missing = new();

        /// <summary>依場景名與日夜挑曲；回傳 null ＝這個場景不放音樂。</summary>
        static string Choose(string scene, bool night) => scene switch
        {
            "main" or "town" => night ? "night" : "day",
            "candy" => night ? "night" : "candy",
            "shop" or "brew" or "garden" => "shop",
            _ => null,
        };

        /// <summary>這個場景的曲子有沒有分日夜（沒有的話 Update 不必看時間）。</summary>
        static bool DependsOnTime(string scene) => scene is "main" or "town" or "candy";

        // ──────────── 常駐物件 ────────────

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        /// <summary>關掉 Domain Reload 進 Play 時，靜態欄位會留著上一輪的東西 —— 這裡清乾淨。</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            instance = null;
            clips.Clear();
            missing.Clear();
        }

        static Bgm Ensure()
        {
            if (instance != null) return instance;
            var go = new GameObject("Bgm");
            DontDestroyOnLoad(go);
            return go.AddComponent<Bgm>();      // Awake 會設 instance
        }

        readonly AudioSource[] src = new AudioSource[2];
        /// <summary>兩個 source 各自的淡變係數 0..1。</summary>
        readonly float[] fade = new float[2];
        /// <summary>現在「應該響」的是哪一個 source（-1 ＝都在淡出、不放音樂）。</summary>
        int live = -1;
        /// <summary>現在選定的曲名（null ＝不放）。跟新選的一樣就不動。</summary>
        string current;
        string scene = "";
        bool night;
        /// <summary>音量設定變了，下一個 Update 要重套一次。</summary>
        bool volumeDirty = true;

        void Awake()
        {
            instance = this;
            for (int i = 0; i < src.Length; i++)
            {
                var s = gameObject.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.loop = true;
                s.spatialBlend = 0f;             // 純 2D
                s.priority = 0;                  // 最高優先：聲音很多時不要被音效擠掉
                s.volume = 0f;
                src[i] = s;
            }
            SceneManager.sceneLoaded += OnSceneLoaded;
            Sfx.Changed += OnSettingsChanged;
            scene = SceneManager.GetActiveScene().name;
            Retarget();
        }

        void OnDestroy()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            Sfx.Changed -= OnSettingsChanged;
            if (instance == this) instance = null;
        }

        void OnSettingsChanged() => volumeDirty = true;

        void OnSceneLoaded(Scene s, LoadSceneMode mode)
        {
            if (mode != LoadSceneMode.Single) return;    // 疊加載入的不算換地方
            scene = s.name;
            Retarget();
        }

        void Update()
        {
            // 日夜交替：只有分日夜的場景才看，而且狀態變了才重選
            if (DependsOnTime(scene) && SafeIsNight() != night) Retarget();

            bool fading = false;
            float step = FadeTime > 0f ? Time.unscaledDeltaTime / FadeTime : 1f;
            for (int i = 0; i < src.Length; i++)
            {
                float goal = i == live ? 1f : 0f;
                if (Mathf.Approximately(fade[i], goal)) continue;
                fade[i] = Mathf.MoveTowards(fade[i], goal, step);
                fading = true;
                if (fade[i] <= 0f && i != live && src[i].isPlaying)
                {
                    src[i].Stop();               // 淡出完就停掉，不要白白解碼
                    src[i].clip = null;
                }
            }
            if (fading || volumeDirty) ApplyVolumes();
        }

        void ApplyVolumes()
        {
            volumeDirty = false;
            float master = Sfx.Muted ? 0f : Sfx.MusicVolume;
            for (int i = 0; i < src.Length; i++)
                if (src[i] != null) src[i].volume = master * fade[i];
        }

        static bool SafeIsNight()
        {
            try { return TimeSystem.IsNight; }
            catch (Exception) { return false; }
        }

        /// <summary>重新選曲；跟現在的一樣就什麼都不做。</summary>
        void Retarget()
        {
            try
            {
                night = DependsOnTime(scene) && SafeIsNight();
                string want = Choose(scene, night);
                if (want == current) return;
                current = want;

                var clip = want == null ? null : Clip(want);
                if (clip == null) { live = -1; return; }   // 不放（或找不到檔）：全部淡出

                // 正在淡出的那個剛好就是要的曲子（例如進門又馬上出來）→ 直接拉回來，不從頭播
                for (int i = 0; i < src.Length; i++)
                {
                    if (src[i].clip == clip && src[i].isPlaying) { live = i; return; }
                }

                // 挑另一個 source 當新的那首（沒有在響的話挑比較小聲的那個）
                int next = live >= 0 ? 1 - live : (fade[0] <= fade[1] ? 0 : 1);
                var s = src[next];
                s.Stop();
                s.clip = clip;
                fade[next] = 0f;
                s.volume = 0f;
                s.Play();
                live = next;
            }
            catch (Exception e)
            {
                // 音樂壞掉不能讓遊戲跟著壞
                if (missing.Add("!" + current)) Debug.LogWarning($"[Bgm] 換曲「{current}」失敗：{e.Message}");
            }
        }

        static AudioClip Clip(string name)
        {
            if (clips.TryGetValue(name, out var c) && c != null) return c;
            if (missing.Contains(name)) return null;

            c = Resources.Load<AudioClip>(Folder + name);
            if (c == null)
            {
                missing.Add(name);       // 只警告一次，之後靜默略過
                Debug.LogWarning($"[Bgm] 找不到音樂 Resources/{Folder}{name}（之後不再提醒）—— " +
                                 "跑一次 python tools/gen_bgm.py 產生佔位曲");
                return null;
            }
            clips[name] = c;
            return c;
        }
    }
}
