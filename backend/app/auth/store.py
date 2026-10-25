import secrets
import threading
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.auth.models import ALL_ARMS, ExperimentArm, ExperimentAssignment, UserRecord


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class InMemoryUserStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users_by_id: dict[UUID, UserRecord] = {}
        self._users_by_email: dict[str, UUID] = {}
        self._assignments_by_user_id: dict[UUID, ExperimentAssignment] = {}
        self._arm_counts: dict[ExperimentArm, int] = {arm: 0 for arm in ALL_ARMS}

    def clear(self) -> None:
        with self._lock:
            self._users_by_id.clear()
            self._users_by_email.clear()
            self._assignments_by_user_id.clear()
            self._arm_counts = {arm: 0 for arm in ALL_ARMS}

    def _choose_arm(self) -> ExperimentArm:
        min_count = min(self._arm_counts.values())
        candidates = [arm for arm, count in self._arm_counts.items() if count == min_count]
        return secrets.choice(candidates)

    def register_user(
        self,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> tuple[UserRecord, ExperimentAssignment]:
        email_clean = email.strip().lower()
        now = datetime.now(UTC)

        with self._lock:
            if email_clean in self._users_by_email:
                raise UserAlreadyExistsError(f"User with email {email_clean} already exists")

            user_id = uuid4()
            arm = self._choose_arm()
            self._arm_counts[arm] += 1

            user = UserRecord(
                id=user_id,
                email=email_clean,
                password_hash=password_hash,
                display_name=display_name.strip(),
                created_at=now,
                consent_at=None,
                deleted_at=None,
            )
            assignment = ExperimentAssignment(
                user_id=user_id,
                arm=arm,
                assigned_at=now,
            )

            self._users_by_id[user_id] = user
            self._users_by_email[email_clean] = user_id
            self._assignments_by_user_id[user_id] = assignment

            return user, assignment

    def get_user_by_email(self, email: str) -> UserRecord | None:
        email_clean = email.strip().lower()
        with self._lock:
            user_id = self._users_by_email.get(email_clean)
            if user_id is None:
                return None
            user = self._users_by_id.get(user_id)
            if user and user.deleted_at is None:
                return user
            return None

    def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        with self._lock:
            user = self._users_by_id.get(user_id)
            if user and user.deleted_at is None:
                return user
            return None

    def get_assignment(self, user_id: UUID) -> ExperimentAssignment | None:
        with self._lock:
            return self._assignments_by_user_id.get(user_id)

    def set_consent(self, user_id: UUID) -> datetime:
        with self._lock:
            user = self._users_by_id.get(user_id)
            if user is None or user.deleted_at is not None:
                raise UserNotFoundError(f"User {user_id} not found")
            now = datetime.now(UTC)
            user.consent_at = now
            return now

    def soft_delete_user(self, user_id: UUID) -> bool:
        with self._lock:
            user = self._users_by_id.get(user_id)
            if user is None or user.deleted_at is not None:
                return False
            user.deleted_at = datetime.now(UTC)
            return True


auth_store = InMemoryUserStore()
