import { _decorator, Component } from 'cc';
const { ccclass } = _decorator;

/**
 * 俯視角的前後遮擋。
 *
 * 掛在裝所有場景物件的容器上（Props）。每幀把子節點依 Y 由大到小排 —— Y 越小
 * 代表越靠畫面下方、離鏡頭越近，就要越晚繪製。這樣女巫走到樹的下面時會擋住樹，
 * 走到樹上面時會被樹擋住。
 *
 * Cocos 的 2D 繪製順序是看節點在階層中的先後（siblingIndex），不是看 z，
 * 所以只能重排。節點只有幾十個，而且順序沒亂掉時直接跳過，成本可以忽略。
 *
 * 前提：每個物件的錨點都是 (0.5, 0)，position.y 才會剛好是「腳踩的位置」。
 */
@ccclass('YSortLayer')
export class YSortLayer extends Component {
    lateUpdate() {
        const kids = this.node.children;
        let sorted = true;
        for (let i = 1; i < kids.length; i++) {
            if (kids[i - 1].position.y < kids[i].position.y) { sorted = false; break; }
        }
        if (sorted) return;

        const order = kids.slice().sort((a, b) => b.position.y - a.position.y);
        for (let i = 0; i < order.length; i++) order[i].setSiblingIndex(i);
    }
}
