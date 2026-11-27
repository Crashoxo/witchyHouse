using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 攝影機跟著女巫跑，並夾在地圖範圍內（不要拍到地圖外的空白）。
    ///
    /// 森林是 2816×1792，畫面只有 960×640，所以一定要跟隨；
    /// 但走到地圖邊緣時攝影機要停住，不然邊界外的黑色會露出來。
    ///
    /// ⚠️ 用 LateUpdate：PlayerController 在 Update 移動角色，這裡才跟得上這一幀的位置，
    ///    不然畫面會抖（角色動了、攝影機下一幀才跟上）。
    /// </summary>
    public class CameraFollow : MonoBehaviour
    {
        [Tooltip("要跟隨的對象（留空會自動找名叫 Player 的物件）")]
        public Transform target;

        [Tooltip("跟隨的柔滑度（0＝硬跟、越大越軟）")]
        public float smooth = 0.12f;

        Camera cam;
        Vector3 vel;
        bool hasBounds;
        float minX, maxX, minY, maxY;

        void Awake()
        {
            cam = GetComponent<Camera>();
            if (target == null)
            {
                var p = GameObject.Find("Player");
                if (p != null) target = p.transform;
            }
            ComputeBounds();
        }

        /// <summary>從場景裡的 Ground 算出攝影機中心可以走到哪，超出去就會拍到地圖外。</summary>
        void ComputeBounds()
        {
            var g = GameObject.Find("Ground");
            if (g == null || !g.TryGetComponent<SpriteRenderer>(out var sr) || cam == null) return;

            float halfH = cam.orthographicSize;
            float halfW = halfH * cam.aspect;
            var b = sr.bounds;

            // 地圖比畫面小的話就不夾（整張都看得到，攝影機停在中間）
            if (b.size.x <= halfW * 2f || b.size.y <= halfH * 2f) return;

            hasBounds = true;
            minX = b.min.x + halfW;
            maxX = b.max.x - halfW;
            minY = b.min.y + halfH;
            maxY = b.max.y - halfH;
        }

        /// <summary>
        /// 由程式指定鏡頭能拍到的世界範圍，取代 Awake 從場景 Ground 量的那份（8-bit 後花園用：場景檔裡的 Ground
        /// 還是舊圖 1376×768，新底圖比它大）。範圍比畫面窄（或矮）的那一軸固定在範圍中線，永遠不會拍到範圍外。
        /// 順便把鏡頭直接擺到夾好的位置（進場不會從原點慢慢滑過去）。
        /// ⚠️ 跟 ComputeBounds 一樣只在呼叫當下量一次 cam.aspect —— 執行中改視窗比例不會重算（所有場景都是這樣）。
        /// </summary>
        public void ClampTo(Rect world)
        {
            if (cam == null) cam = GetComponent<Camera>();
            if (cam == null) return;
            float halfH = cam.orthographicSize;
            float halfW = halfH * cam.aspect;
            hasBounds = true;
            if (world.width <= halfW * 2f) minX = maxX = world.center.x;
            else { minX = world.xMin + halfW; maxX = world.xMax - halfW; }
            if (world.height <= halfH * 2f) minY = maxY = world.center.y;
            else { minY = world.yMin + halfH; maxY = world.yMax - halfH; }
            if (target != null)
            {
                transform.position = new Vector3(Mathf.Clamp(target.position.x, minX, maxX),
                                                 Mathf.Clamp(target.position.y, minY, maxY), transform.position.z);
                vel = Vector3.zero;
            }
        }

        void LateUpdate()
        {
            if (target == null) return;

            var want = new Vector3(target.position.x, target.position.y, transform.position.z);
            if (hasBounds)
            {
                want.x = Mathf.Clamp(want.x, minX, maxX);
                want.y = Mathf.Clamp(want.y, minY, maxY);
            }

            transform.position = smooth <= 0f
                ? want
                : Vector3.SmoothDamp(transform.position, want, ref vel, smooth);
        }
    }
}
