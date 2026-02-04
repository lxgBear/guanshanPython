"""AchievementDraft 实体单元测试

测试覆盖:
- 实体创建与默认值
- 权限检查 (can_edit, can_submit, can_review)
- 工作流操作 (submit_for_review, approve, forward, return_to_author, return_to_previous, void)
- 退回后重新提交流程
- 数据转换 (to_dict, MongoDB 文档转换)
"""

import pytest
from datetime import datetime

from src.core.domain.entities.achievement_draft import (
    AchievementDraft,
    AchievementStatus,
    achievement_draft_to_mongo_doc,
    mongo_doc_to_achievement_draft,
)


class TestAchievementDraftCreation:
    """AchievementDraft 创建测试"""

    def test_create_draft_with_defaults(self):
        """测试创建草稿时的默认值"""
        draft = AchievementDraft()

        assert draft.id is not None
        assert draft.title == ""
        assert draft.description == ""
        assert draft.summary == ""
        assert draft.combined_content == ""
        assert draft.tags == []
        assert draft.primary_category == ""
        assert draft.secondary_category == ""
        assert draft.tertiary_category == ""
        assert draft.source_entry_ids == []
        assert draft.raw_data_count == 0
        assert draft.author_id == ""
        assert draft.author_name == ""
        assert draft.status == AchievementStatus.DRAFT
        assert draft.current_reviewer_id == ""
        assert draft.current_reviewer_name == ""
        assert draft.current_review_level == 0
        assert draft.returned_by_reviewer_id == ""
        assert draft.returned_by_reviewer_name == ""
        assert draft.returned_at_level == 0
        assert draft.created_at is not None
        assert draft.updated_at is not None
        assert draft.submitted_at is None
        assert draft.completed_at is None

    def test_create_draft_with_values(self):
        """测试使用指定值创建草稿"""
        draft = AchievementDraft(
            title="测试标题",
            description="测试描述",
            summary="测试摘要",
            combined_content="<p>测试内容</p>",
            tags=["标签1", "标签2"],
            primary_category="大类",
            secondary_category="类别",
            tertiary_category="地域",
            author_id="user_123",
            author_name="张三",
            source_entry_ids=["entry_1", "entry_2", "entry_3"],
        )

        assert draft.title == "测试标题"
        assert draft.description == "测试描述"
        assert draft.summary == "测试摘要"
        assert draft.combined_content == "<p>测试内容</p>"
        assert draft.tags == ["标签1", "标签2"]
        assert draft.primary_category == "大类"
        assert draft.secondary_category == "类别"
        assert draft.tertiary_category == "地域"
        assert draft.author_id == "user_123"
        assert draft.author_name == "张三"
        assert draft.source_entry_ids == ["entry_1", "entry_2", "entry_3"]
        assert draft.raw_data_count == 3  # 自动计算
        assert draft.status == AchievementStatus.DRAFT

    def test_raw_data_count_auto_calculated(self):
        """测试 raw_data_count 自动计算"""
        draft = AchievementDraft(
            source_entry_ids=["entry_1", "entry_2"],
        )
        assert draft.raw_data_count == 2

        # 修改 source_entry_ids 后需要手动更新
        draft.source_entry_ids.append("entry_3")
        draft.update_raw_data_count()
        assert draft.raw_data_count == 3


class TestAchievementDraftCanEdit:
    """can_edit 权限测试"""

    def test_can_edit_draft_status_author(self):
        """测试草稿状态下作者可以编辑"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_edit("user_123") is True

    def test_can_edit_draft_status_other_user(self):
        """测试草稿状态下其他用户不能编辑"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_edit("other_user") is False

    def test_can_edit_pending_review_status(self):
        """测试待审核状态下任何人都不能编辑"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.can_edit("user_123") is False
        assert draft.can_edit("reviewer_1") is False

    def test_can_edit_returned_status_author(self):
        """测试退回状态下作者可以编辑"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.can_edit("user_123") is True

    def test_can_edit_returned_status_other_user(self):
        """测试退回状态下其他用户不能编辑"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.can_edit("other_user") is False

    def test_can_edit_approved_status(self):
        """测试已通过状态下不能编辑"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        assert draft.can_edit("user_123") is False

    def test_can_edit_voided_status(self):
        """测试已作废状态下不能编辑"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.void()

        assert draft.can_edit("user_123") is False

    def test_can_edit_empty_user_id(self):
        """测试空用户ID不能编辑"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_edit("") is False
        assert draft.can_edit(None) is False

    def test_can_edit_empty_author_id(self):
        """测试空作者ID时不能编辑"""
        draft = AchievementDraft(author_id="")
        assert draft.can_edit("user_123") is False


class TestAchievementDraftCanSubmit:
    """can_submit 权限测试"""

    def test_can_submit_draft_status_author(self):
        """测试草稿状态下作者可以提交"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_submit("user_123") is True

    def test_can_submit_draft_status_other_user(self):
        """测试草稿状态下其他用户不能提交"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_submit("other_user") is False

    def test_can_submit_pending_review_status(self):
        """测试待审核状态下不能提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.can_submit("user_123") is False

    def test_can_submit_returned_status_author(self):
        """测试退回状态下作者可以提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.can_submit("user_123") is True

    def test_can_submit_approved_status(self):
        """测试已通过状态下不能提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        assert draft.can_submit("user_123") is False

    def test_can_submit_empty_user_id(self):
        """测试空用户ID不能提交"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_submit("") is False
        assert draft.can_submit(None) is False


class TestAchievementDraftCanReview:
    """can_review 权限测试"""

    def test_can_review_pending_status_current_reviewer(self):
        """测试待审核状态下当前审核员可以审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.can_review("reviewer_1") is True

    def test_can_review_pending_status_other_reviewer(self):
        """测试待审核状态下其他人不能审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.can_review("reviewer_2") is False
        assert draft.can_review("user_123") is False

    def test_can_review_draft_status(self):
        """测试草稿状态下不能审核"""
        draft = AchievementDraft(author_id="user_123")
        assert draft.can_review("reviewer_1") is False

    def test_can_review_returned_status(self):
        """测试退回状态下不能审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.can_review("reviewer_1") is False

    def test_can_review_approved_status(self):
        """测试已通过状态下不能审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        assert draft.can_review("reviewer_1") is False

    def test_can_review_empty_user_id(self):
        """测试空用户ID不能审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.can_review("") is False
        assert draft.can_review(None) is False


class TestSubmitForReview:
    """submit_for_review 工作流测试"""

    def test_submit_for_review_from_draft(self):
        """测试从草稿状态提交审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        assert draft.status == AchievementStatus.PENDING_REVIEW
        assert draft.current_reviewer_id == "reviewer_1"
        assert draft.current_reviewer_name == "审核员A"
        assert draft.current_review_level == 1
        assert draft.submitted_at is not None

    def test_submit_for_review_missing_reviewer_id(self):
        """测试提交审核时缺少审核员ID"""
        draft = AchievementDraft(author_id="user_123")

        with pytest.raises(ValueError, match="missing reviewer information"):
            draft.submit_for_review("", "审核员A")

    def test_submit_for_review_missing_reviewer_name(self):
        """测试提交审核时缺少审核员姓名"""
        draft = AchievementDraft(author_id="user_123")

        with pytest.raises(ValueError, match="missing reviewer information"):
            draft.submit_for_review("reviewer_1", "")

    def test_submit_for_review_from_pending_status(self):
        """测试从待审核状态不能再次提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        with pytest.raises(ValueError, match="Cannot submit"):
            draft.submit_for_review("reviewer_2", "审核员B")

    def test_submit_for_review_from_approved_status(self):
        """测试从已通过状态不能提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        with pytest.raises(ValueError, match="Cannot submit"):
            draft.submit_for_review("reviewer_2", "审核员B")


class TestApprove:
    """approve 工作流测试"""

    def test_approve_from_pending_review(self):
        """测试从待审核状态通过审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        assert draft.status == AchievementStatus.APPROVED
        assert draft.completed_at is not None

    def test_approve_from_draft_status(self):
        """测试从草稿状态不能通过审核"""
        draft = AchievementDraft(author_id="user_123")

        with pytest.raises(ValueError, match="Cannot approve"):
            draft.approve()

    def test_approve_from_returned_status(self):
        """测试从退回状态不能直接通过审核"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        with pytest.raises(ValueError, match="Cannot approve"):
            draft.approve()

    def test_approve_from_approved_status(self):
        """测试从已通过状态不能再次通过"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        with pytest.raises(ValueError, match="Cannot approve"):
            draft.approve()


class TestForward:
    """forward 工作流测试"""

    def test_forward_to_next_reviewer(self):
        """测试转交到下一级审核员"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")

        assert draft.status == AchievementStatus.PENDING_REVIEW
        assert draft.current_reviewer_id == "reviewer_2"
        assert draft.current_reviewer_name == "审核员B"
        assert draft.current_review_level == 2

    def test_forward_multiple_times(self):
        """测试多次转交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")
        draft.forward("reviewer_3", "审核员C")

        assert draft.current_reviewer_id == "reviewer_3"
        assert draft.current_reviewer_name == "审核员C"
        assert draft.current_review_level == 3

    def test_forward_missing_reviewer_id(self):
        """测试转交时缺少审核员ID"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        with pytest.raises(ValueError, match="missing next reviewer information"):
            draft.forward("", "审核员B")

    def test_forward_missing_reviewer_name(self):
        """测试转交时缺少审核员姓名"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")

        with pytest.raises(ValueError, match="missing next reviewer information"):
            draft.forward("reviewer_2", "")

    def test_forward_from_draft_status(self):
        """测试从草稿状态不能转交"""
        draft = AchievementDraft(author_id="user_123")

        with pytest.raises(ValueError, match="Cannot forward"):
            draft.forward("reviewer_1", "审核员A")

    def test_forward_from_approved_status(self):
        """测试从已通过状态不能转交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        with pytest.raises(ValueError, match="Cannot forward"):
            draft.forward("reviewer_2", "审核员B")


class TestReturnToAuthor:
    """return_to_author 工作流测试"""

    def test_return_to_author_from_pending_review(self):
        """测试从待审核状态退回提交人"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        assert draft.status == AchievementStatus.RETURNED
        assert draft.returned_by_reviewer_id == "reviewer_1"
        assert draft.returned_by_reviewer_name == "审核员A"
        assert draft.returned_at_level == 1
        assert draft.current_reviewer_id == ""
        assert draft.current_reviewer_name == ""

    def test_return_to_author_from_higher_level(self):
        """测试从更高级别退回提交人"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")
        draft.forward("reviewer_3", "审核员C")
        draft.return_to_author()

        assert draft.status == AchievementStatus.RETURNED
        assert draft.returned_by_reviewer_id == "reviewer_3"
        assert draft.returned_by_reviewer_name == "审核员C"
        assert draft.returned_at_level == 3

    def test_return_to_author_from_draft_status(self):
        """测试从草稿状态不能退回"""
        draft = AchievementDraft(author_id="user_123")

        with pytest.raises(ValueError, match="Cannot return to author"):
            draft.return_to_author()

    def test_return_to_author_from_approved_status(self):
        """测试从已通过状态不能退回"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        with pytest.raises(ValueError, match="Cannot return to author"):
            draft.return_to_author()


class TestReturnToPrevious:
    """return_to_previous 工作流测试"""

    def test_return_to_previous_reviewer(self):
        """测试退回上一级审核员"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")
        draft.return_to_previous("reviewer_1", "审核员A", 1)

        assert draft.status == AchievementStatus.PENDING_REVIEW
        assert draft.current_reviewer_id == "reviewer_1"
        assert draft.current_reviewer_name == "审核员A"
        assert draft.current_review_level == 1

    def test_return_to_previous_from_level_3(self):
        """测试从第三级退回第二级"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")
        draft.forward("reviewer_3", "审核员C")
        draft.return_to_previous("reviewer_2", "审核员B", 2)

        assert draft.current_reviewer_id == "reviewer_2"
        assert draft.current_review_level == 2

    def test_return_to_previous_missing_reviewer_id(self):
        """测试退回上一级时缺少审核员ID"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")

        with pytest.raises(ValueError, match="missing previous reviewer information"):
            draft.return_to_previous("", "审核员A", 1)

    def test_return_to_previous_missing_reviewer_name(self):
        """测试退回上一级时缺少审核员姓名"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")

        with pytest.raises(ValueError, match="missing previous reviewer information"):
            draft.return_to_previous("reviewer_1", "", 1)

    def test_return_to_previous_invalid_level(self):
        """测试退回上一级时层级无效"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")

        with pytest.raises(ValueError, match="invalid previous level"):
            draft.return_to_previous("reviewer_1", "审核员A", 0)

        with pytest.raises(ValueError, match="invalid previous level"):
            draft.return_to_previous("reviewer_1", "审核员A", -1)

    def test_return_to_previous_from_draft_status(self):
        """测试从草稿状态不能退回上一级"""
        draft = AchievementDraft(author_id="user_123")

        with pytest.raises(ValueError, match="Cannot return to previous"):
            draft.return_to_previous("reviewer_1", "审核员A", 1)


class TestResubmitAfterReturn:
    """退回后重新提交测试"""

    def test_resubmit_after_return_goes_to_original_reviewer(self):
        """测试退回后重新提交应该回到退回的审核员"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        # 重新提交时传入的审核员信息应该被忽略
        draft.submit_for_review("reviewer_2", "审核员B")

        assert draft.current_reviewer_id == "reviewer_1"
        assert draft.current_reviewer_name == "审核员A"
        assert draft.current_review_level == 1
        assert draft.status == AchievementStatus.PENDING_REVIEW

    def test_resubmit_after_return_from_higher_level(self):
        """测试从更高级别退回后重新提交"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.forward("reviewer_2", "审核员B")
        draft.forward("reviewer_3", "审核员C")
        draft.return_to_author()

        # 重新提交应该回到退回的审核员 (reviewer_3)
        draft.submit_for_review("any_reviewer", "任意审核员")

        assert draft.current_reviewer_id == "reviewer_3"
        assert draft.current_reviewer_name == "审核员C"
        assert draft.current_review_level == 3

    def test_resubmit_clears_return_info(self):
        """测试重新提交后清除退回信息"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()
        draft.submit_for_review("reviewer_2", "审核员B")

        assert draft.returned_by_reviewer_id == ""
        assert draft.returned_by_reviewer_name == ""
        assert draft.returned_at_level == 0


class TestVoid:
    """void 工作流测试"""

    def test_void_from_draft(self):
        """测试从草稿状态作废"""
        draft = AchievementDraft(author_id="user_123")
        draft.void()

        assert draft.status == AchievementStatus.VOIDED
        assert draft.completed_at is not None

    def test_void_from_pending_review(self):
        """测试从待审核状态作废"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.void()

        assert draft.status == AchievementStatus.VOIDED
        assert draft.completed_at is not None

    def test_void_from_returned(self):
        """测试从退回状态作废"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()
        draft.void()

        assert draft.status == AchievementStatus.VOIDED

    def test_void_from_approved_status(self):
        """测试从已通过状态不能作废"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()

        with pytest.raises(ValueError, match="Cannot void"):
            draft.void()

    def test_void_from_voided_status(self):
        """测试从已作废状态不能再次作废"""
        draft = AchievementDraft(author_id="user_123")
        draft.void()

        with pytest.raises(ValueError, match="Cannot void"):
            draft.void()


class TestToDict:
    """to_dict 转换测试"""

    def test_to_dict_basic(self):
        """测试基本字典转换"""
        draft = AchievementDraft(
            title="测试标题",
            description="测试描述",
            author_id="user_123",
            author_name="张三",
        )

        d = draft.to_dict()

        assert d["title"] == "测试标题"
        assert d["description"] == "测试描述"
        assert d["author_id"] == "user_123"
        assert d["author_name"] == "张三"
        assert d["status"] == "draft"
        assert d["current_review_level"] == 0

    def test_to_dict_all_fields(self):
        """测试所有字段的字典转换"""
        draft = AchievementDraft(
            title="测试",
            description="描述",
            summary="摘要",
            combined_content="内容",
            tags=["标签1", "标签2"],
            primary_category="大类",
            secondary_category="类别",
            tertiary_category="地域",
            source_entry_ids=["entry_1", "entry_2"],
            author_id="user_123",
            author_name="张三",
        )

        d = draft.to_dict()

        assert "id" in d
        assert d["title"] == "测试"
        assert d["description"] == "描述"
        assert d["summary"] == "摘要"
        assert d["combined_content"] == "内容"
        assert d["tags"] == ["标签1", "标签2"]
        assert d["primary_category"] == "大类"
        assert d["secondary_category"] == "类别"
        assert d["tertiary_category"] == "地域"
        assert d["source_entry_ids"] == ["entry_1", "entry_2"]
        assert d["raw_data_count"] == 2
        assert d["author_id"] == "user_123"
        assert d["author_name"] == "张三"
        assert d["status"] == "draft"
        assert d["current_reviewer_id"] == ""
        assert d["current_reviewer_name"] == ""
        assert d["current_review_level"] == 0
        assert d["created_at"] is not None
        assert d["updated_at"] is not None
        assert d["submitted_at"] is None
        assert d["completed_at"] is None

    def test_to_dict_status_values(self):
        """测试不同状态的字典转换"""
        draft = AchievementDraft(author_id="user_123")

        # Draft status
        assert draft.to_dict()["status"] == "draft"

        # Pending review status
        draft.submit_for_review("reviewer_1", "审核员A")
        assert draft.to_dict()["status"] == "pending_review"

        # Returned status
        draft.return_to_author()
        assert draft.to_dict()["status"] == "returned"

        # Resubmit and approve
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.approve()
        assert draft.to_dict()["status"] == "approved"

    def test_to_dict_timestamps_as_isoformat(self):
        """测试时间戳转换为 ISO 格式"""
        draft = AchievementDraft(author_id="user_123")

        d = draft.to_dict()

        assert isinstance(d["created_at"], str)
        assert isinstance(d["updated_at"], str)
        # 验证是 ISO 格式
        datetime.fromisoformat(d["created_at"])
        datetime.fromisoformat(d["updated_at"])


class TestMongoDocConversion:
    """MongoDB 文档转换测试"""

    def test_to_mongo_doc_basic(self):
        """测试基本 MongoDB 文档转换"""
        draft = AchievementDraft(
            title="测试标题",
            author_id="user_123",
            author_name="张三",
            source_entry_ids=["entry_1"],
        )

        doc = achievement_draft_to_mongo_doc(draft)

        assert doc["_id"] == draft.id
        assert doc["title"] == "测试标题"
        assert doc["author_id"] == "user_123"
        assert doc["author_name"] == "张三"
        assert doc["source_entry_ids"] == ["entry_1"]
        assert doc["status"] == "draft"

    def test_to_mongo_doc_includes_return_info(self):
        """测试 MongoDB 文档包含退回信息"""
        draft = AchievementDraft(author_id="user_123")
        draft.submit_for_review("reviewer_1", "审核员A")
        draft.return_to_author()

        doc = achievement_draft_to_mongo_doc(draft)

        assert doc["returned_by_reviewer_id"] == "reviewer_1"
        assert doc["returned_by_reviewer_name"] == "审核员A"
        assert doc["returned_at_level"] == 1

    def test_from_mongo_doc_basic(self):
        """测试基本 MongoDB 文档解析"""
        doc = {
            "_id": "test_id",
            "title": "测试标题",
            "description": "测试描述",
            "author_id": "user_123",
            "author_name": "张三",
            "status": "draft",
            "source_entry_ids": ["entry_1", "entry_2"],
            "raw_data_count": 2,
        }

        draft = mongo_doc_to_achievement_draft(doc)

        assert draft.id == "test_id"
        assert draft.title == "测试标题"
        assert draft.description == "测试描述"
        assert draft.author_id == "user_123"
        assert draft.author_name == "张三"
        assert draft.status == AchievementStatus.DRAFT
        assert draft.source_entry_ids == ["entry_1", "entry_2"]
        assert draft.raw_data_count == 2

    def test_from_mongo_doc_all_statuses(self):
        """测试解析所有状态值"""
        for status in AchievementStatus:
            doc = {"_id": "test_id", "status": status.value}
            draft = mongo_doc_to_achievement_draft(doc)
            assert draft.status == status

    def test_from_mongo_doc_invalid_status_defaults_to_draft(self):
        """测试无效状态值默认为草稿"""
        doc = {"_id": "test_id", "status": "invalid_status"}
        draft = mongo_doc_to_achievement_draft(doc)
        assert draft.status == AchievementStatus.DRAFT

    def test_from_mongo_doc_missing_status_defaults_to_draft(self):
        """测试缺少状态值默认为草稿"""
        doc = {"_id": "test_id"}
        draft = mongo_doc_to_achievement_draft(doc)
        assert draft.status == AchievementStatus.DRAFT

    def test_roundtrip_conversion(self):
        """测试往返转换"""
        original = AchievementDraft(
            title="测试标题",
            description="测试描述",
            summary="测试摘要",
            combined_content="<p>内容</p>",
            tags=["标签1", "标签2"],
            primary_category="大类",
            secondary_category="类别",
            tertiary_category="地域",
            source_entry_ids=["entry_1", "entry_2"],
            author_id="user_123",
            author_name="张三",
        )

        doc = achievement_draft_to_mongo_doc(original)
        restored = mongo_doc_to_achievement_draft(doc)

        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.description == original.description
        assert restored.summary == original.summary
        assert restored.combined_content == original.combined_content
        assert restored.tags == original.tags
        assert restored.primary_category == original.primary_category
        assert restored.secondary_category == original.secondary_category
        assert restored.tertiary_category == original.tertiary_category
        assert restored.source_entry_ids == original.source_entry_ids
        assert restored.raw_data_count == original.raw_data_count
        assert restored.author_id == original.author_id
        assert restored.author_name == original.author_name
        assert restored.status == original.status

    def test_roundtrip_with_workflow_state(self):
        """测试带工作流状态的往返转换"""
        original = AchievementDraft(author_id="user_123", author_name="张三")
        original.submit_for_review("reviewer_1", "审核员A")
        original.forward("reviewer_2", "审核员B")
        original.return_to_author()

        doc = achievement_draft_to_mongo_doc(original)
        restored = mongo_doc_to_achievement_draft(doc)

        assert restored.status == AchievementStatus.RETURNED
        assert restored.returned_by_reviewer_id == "reviewer_2"
        assert restored.returned_by_reviewer_name == "审核员B"
        assert restored.returned_at_level == 2

    def test_from_mongo_doc_with_datetime_objects(self):
        """测试解析带 datetime 对象的文档"""
        now = datetime.utcnow()
        doc = {
            "_id": "test_id",
            "created_at": now,
            "updated_at": now,
            "submitted_at": now,
            "completed_at": now,
        }

        draft = mongo_doc_to_achievement_draft(doc)

        assert draft.created_at == now
        assert draft.updated_at == now
        assert draft.submitted_at == now
        assert draft.completed_at == now

    def test_from_mongo_doc_with_none_timestamps(self):
        """测试解析带 None 时间戳的文档"""
        doc = {
            "_id": "test_id",
            "created_at": None,
            "updated_at": None,
            "submitted_at": None,
            "completed_at": None,
        }

        draft = mongo_doc_to_achievement_draft(doc)

        # created_at 和 updated_at 应该有默认值
        assert draft.created_at is not None
        assert draft.updated_at is not None
        # submitted_at 和 completed_at 应该为 None
        assert draft.submitted_at is None
        assert draft.completed_at is None


class TestAchievementStatus:
    """AchievementStatus 枚举测试"""

    def test_status_values(self):
        """测试状态枚举值"""
        assert AchievementStatus.DRAFT.value == "draft"
        assert AchievementStatus.PENDING_REVIEW.value == "pending_review"
        assert AchievementStatus.RETURNED.value == "returned"
        assert AchievementStatus.APPROVED.value == "approved"
        assert AchievementStatus.VOIDED.value == "voided"

    def test_status_from_value(self):
        """测试从值创建状态"""
        assert AchievementStatus("draft") == AchievementStatus.DRAFT
        assert AchievementStatus("pending_review") == AchievementStatus.PENDING_REVIEW
        assert AchievementStatus("returned") == AchievementStatus.RETURNED
        assert AchievementStatus("approved") == AchievementStatus.APPROVED
        assert AchievementStatus("voided") == AchievementStatus.VOIDED

    def test_invalid_status_value(self):
        """测试无效状态值"""
        with pytest.raises(ValueError):
            AchievementStatus("invalid")
