# tests/pages/locators.py
"""共享 Locator 工厂函数 — 集中管理常用 .or_() 回退链，减少重复代码"""


# ==================== 弹窗/对话框 ====================


def dialog(page):
    """获取当前打开的 dialog 或 alertdialog"""
    return page.locator("[role=dialog]").or_(page.locator("[role=alertdialog]"))


def alert_dialog(page):
    """获取 alertdialog"""
    return page.locator("[role=alertdialog]")


# ==================== 按钮回退链 ====================


def confirm_button(container):
    """确认/确定/删除 按钮（用于 alertdialog 或 dialog）"""
    return container.get_by_role("button", name="确认").or_(
        container.get_by_role("button", name="确定").or_(
            container.get_by_role("button", name="删除")
        )
    )


def cancel_button(container):
    """取消/Cancel 按钮"""
    return container.get_by_role("button", name="取消").or_(
        container.get_by_role("button", name="Cancel")
    )


def save_or_submit_button(container):
    """保存/创建/提交 按钮"""
    return container.get_by_role("button", name="保存").or_(
        container.get_by_role("button", name="创建").or_(
            container.locator("button[type=submit]")
        )
    )


def create_button(page):
    """新建/创建/添加 按钮"""
    return page.get_by_role("button", name="新建").or_(
        page.get_by_role("button", name="创建").or_(
            page.get_by_role("button", name="添加")
        )
    )


def delete_button(container):
    """删除 按钮（文本或图标）"""
    return container.get_by_role("button", name="删除").or_(
        container.locator("button").filter(
            has=container.locator("svg.lucide-trash-2, svg.lucide-trash")
        )
    )


def edit_button(container):
    """编辑 按钮（文本或图标）"""
    return container.get_by_role("button", name="编辑").or_(
        container.locator("button").filter(
            has=container.locator("svg.lucide-pencil, svg.lucide-edit")
        )
    )


def close_button(container):
    """关闭 按钮"""
    return container.locator("button[data-slot='dialog-close']").or_(
        container.get_by_role("button", name="关闭")
    )


def search_or_submit_button(page):
    """搜索/检索/提交 按钮"""
    return page.get_by_role("button", name="搜索").or_(
        page.get_by_role("button", name="检索").or_(
            page.locator("button[type=submit]")
        )
    )


def run_or_execute_button(page):
    """运行/执行 按钮"""
    return page.get_by_role("button", name="运行").or_(
        page.get_by_role("button", name="执行")
    )


# ==================== Tab 回退链 ====================


def tab_by_name(page, name):
    """按名称查找 Tab（role=tab 或 button）"""
    return page.get_by_role("tab", name=name).or_(
        page.locator("button").filter(has_text=name).or_(
            page.locator("[role=tab]").filter(has_text=name)
        )
    )


# ==================== 功能按钮回退链 ====================


def button_by_name_or_title(page, name):
    """按 name/title/has_text 查找按钮"""
    return page.get_by_role("button", name=name).or_(
        page.locator(f"button[title='{name}']").or_(
            page.locator("button").filter(has_text=name)
        )
    )
