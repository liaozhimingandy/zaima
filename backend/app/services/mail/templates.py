"""邮件模板：中性措辞，明确「未确认 ≠ 死亡/事故」。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.timeutil import ensure_utc, resolve_tz


@dataclass
class AlertEmailContext:
    guardian_name: str
    period_days: int
    last_checkin_at: datetime | None
    due_at: datetime
    triggered_at: datetime
    overdue_hours: int
    timezone: str


def _fmt(value: datetime | None, timezone: str) -> str:
    if value is None:
        return "尚未确认过"
    tz = resolve_tz(timezone)
    local = ensure_utc(value).astimezone(tz)  # type: ignore[union-attr]
    return local.strftime("%Y-%m-%d %H:%M")


def render_alert_email(ctx: AlertEmailContext) -> tuple[str, str, str]:
    """返回 (subject, text, html)。"""
    who = ctx.guardian_name or "你好"
    last = _fmt(ctx.last_checkin_at, ctx.timezone)
    due = _fmt(ctx.due_at, ctx.timezone)
    fired = _fmt(ctx.triggered_at, ctx.timezone)
    subject = f"【在吗】你关注的人已超过 {ctx.overdue_hours} 小时未完成安全确认"

    text = f"""{who}：

你被设置为「在吗」App 的守护人，当对方长时间未点「我在」时，系统会给你发这封提醒邮件。

- 确认周期：每 {ctx.period_days} 天一次
- 最近一次确认：{last}
- 应确认时间：{due}
- 提醒生成时间：{fired}
- 已超时：约 {ctx.overdue_hours} 小时

请注意：这只是「长时间未完成确认」，并不代表对方发生了事故、疾病或死亡。
可能只是手机没电、忘记点击或暂时不方便。

建议你主动通过电话、微信或其他方式联系对方，确认实际情况。

—— 在吗
（本邮件由系统自动发送，请勿直接回复。若你不再是对方的守护人，可忽略本邮件。）
"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><body style="margin:0;padding:24px;background:#f6f7f9;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px 24px;border:1px solid #eceef2;">
    <div style="font-size:13px;color:#8a8f99;letter-spacing:2px;">在吗 · 安全确认</div>
    <h1 style="font-size:20px;color:#1a1c1f;margin:12px 0 4px;">你关注的人已超过 {ctx.overdue_hours} 小时未完成确认</h1>
    <p style="font-size:14px;color:#5b6270;line-height:1.7;margin:16px 0;">{who}，你好。你被设置为对方的守护人。以下信息供你判断是否需要主动联系：</p>
    <table style="width:100%;font-size:14px;color:#1a1c1f;border-collapse:collapse;">
      <tr><td style="padding:8px 0;color:#8a8f99;width:120px;">确认周期</td><td style="padding:8px 0;">每 {ctx.period_days} 天一次</td></tr>
      <tr><td style="padding:8px 0;color:#8a8f99;">最近一次确认</td><td style="padding:8px 0;">{last}</td></tr>
      <tr><td style="padding:8px 0;color:#8a8f99;">应确认时间</td><td style="padding:8px 0;">{due}</td></tr>
      <tr><td style="padding:8px 0;color:#8a8f99;">提醒生成时间</td><td style="padding:8px 0;">{fired}</td></tr>
    </table>
    <div style="margin-top:20px;padding:14px 16px;background:#fff8e8;border-radius:10px;font-size:13px;color:#7a5a00;line-height:1.7;">
      请注意：这只是「长时间未完成确认」，并不代表对方发生了事故、疾病或死亡。可能只是手机没电、忘记点击或暂时不方便。建议你主动联系对方确认情况。
    </div>
    <p style="margin-top:24px;font-size:12px;color:#a0a5ad;line-height:1.7;">本邮件由系统自动发送，请勿直接回复。若你不再是对方的守护人，可忽略本邮件。</p>
  </div>
</body></html>"""
    return subject, text, html
