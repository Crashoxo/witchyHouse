using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 魔法彈：被 PlayerController 生成後呼叫 Fire(dir) 決定飛行方向，
    /// 飛一段時間就自己消失。之後要加「碰到敵人造成傷害」也是在這支處理碰撞。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版是把一個 Prefab 拖進 PlayerController 的 @property，我這邊沒有那個
    /// prefab（它不在我搬過來的資產裡），所以彈體的圖是**程式生成的一顆發光小球**。
    /// 之後有正式美術就把 Sprite 換掉即可，飛行邏輯不用動。
    /// </summary>
    public class SpellProjectile : MonoBehaviour
    {
        [Tooltip("飛行速度（像素/秒）")] public float speed = 400f;
        [Tooltip("幾秒後自動消失，避免無限累積")] public float lifeTime = 2f;

        Vector2 velocity;
        float age;

        /// <summary>生一顆魔法彈並發射。</summary>
        public static SpellProjectile Spawn(Vector3 from, Vector2 dir)
        {
            var go = new GameObject("Spell");
            go.transform.position = from;

            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = OrbSprite();
            sr.color = new Color32(190, 160, 255, 235);
            sr.sortingOrder = 9000;
            go.transform.localScale = Vector3.one * 0.26f;   // 32px 的圖 → 約 8px 的小球

            var s = go.AddComponent<SpellProjectile>();
            s.Fire(dir);
            return s;
        }

        /// <summary>由玩家角色呼叫，dir ＝ 玩家當下面向。</summary>
        public void Fire(Vector2 dir)
        {
            velocity = dir.sqrMagnitude == 0f ? Vector2.right : dir.normalized;
            velocity *= speed;
        }

        void Update()
        {
            transform.position += (Vector3)(velocity * Time.deltaTime);
            age += Time.deltaTime;
            if (age >= lifeTime)
            {
                // 消失的「噗」。目前還沒有命中判定，之後加碰撞時命中那一處也叫同一個音效。
                // 飛出畫面外才消失的就不響 —— 看不到的東西發出聲音只會讓人困惑。
                if (OnScreen()) Sfx.Play("spell-hit", 0.8f);
                Destroy(gameObject);
            }
        }

        bool OnScreen()
        {
            var cam = Camera.main;
            if (cam == null) return false;
            var v = cam.WorldToViewportPoint(transform.position);
            return v.x >= 0f && v.x <= 1f && v.y >= 0f && v.y <= 1f;
        }

        static Sprite orb;

        /// <summary>發光小球（程式生成，中心亮、邊緣淡出）。</summary>
        static Sprite OrbSprite()
        {
            if (orb != null) return orb;
            const int N = 32;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = Vector2.Distance(new Vector2(x, y), new Vector2(c, c)) / c;
                    float a = Mathf.Clamp01(1f - d);
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a * a * a));   // 中心集中一點
                }
            tex.Apply();
            orb = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), 1f);
            return orb;
        }
    }
}
