# コーディング規約

## 1. 関数の順序（必須）

ファイル内では、主処理を上、呼び出される補助関数を下に置き、caller から callee へ読み下せる配置にする。これは読む順序の規則であり、実行順序とは関係ない。

## 2. 単一責務

関数・コンポーネントは1つの責務だけを持つ。行数だけを理由に分割しない。

## 3. 名前

意味のある名前を付ける。`data` や `process` のような曖昧な名前は、文脈で意味が明確な場合を除き避ける。

## 4. コメント

理由や制約を書く。コードの言い換えは書かない。説明が不要ならコメントは付けない。

## 5. 空行

関連する宣言や操作を目的ごとにまとめ、まとまりの間に空行を置く。変数を全部一括にせず、1変数ごとの機械的な空行も入れない。

## 例

```ts
type Item = { price: number; quantity: number };

export function formatOrderTotal(items: Item[], taxRate: number): string {
  const subtotal = calculateSubtotal(items);
  const tax = subtotal * taxRate;

  return formatYen(subtotal + tax);
}

function calculateSubtotal(items: Item[]): number {
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

function formatYen(amount: number): string {
  return `¥${Math.round(amount).toLocaleString("ja-JP")}`;
}
```