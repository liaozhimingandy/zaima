<template>
  <view class="zm-page">
    <NavBar title="守护人" show-back />

    <view class="intro">
      <text class="intro__title">他们会收到你的提醒邮件</text>
      <text class="intro__text">
        守护人不需要注册账户，只要填写邮箱即可。当你长时间未点「我在」时，系统会给他们发一封中性措辞的提醒邮件。
      </text>
    </view>

    <view class="counter">
      <text class="counter__text">已添加 {{ guardianStore.items.length }} / {{ guardianStore.maxCount }} 位</text>
      <text class="counter__hint">最多 3 位</text>
    </view>

    <StateView
      v-if="guardianStore.loading && guardianStore.items.length === 0"
      type="loading"
      title="正在加载守护人"
    />

    <StateView
      v-else-if="guardianStore.error && guardianStore.items.length === 0"
      type="error"
      title="加载失败"
      :description="guardianStore.error"
      action-text="重试"
      @action="reload"
    />

    <StateView
      v-else-if="guardianStore.items.length === 0"
      type="empty"
      title="还没有守护人"
      description="添加一位你信任的人，异常时他/她会收到邮件提醒"
      action-text="添加守护人"
      @action="openCreate"
    />

    <view v-else class="list">
      <view v-for="guardian in guardianStore.items" :key="guardian.id" class="guardian">
        <view class="guardian__main">
          <view class="guardian__avatar">
            <text class="guardian__avatar-text">{{ guardian.name.slice(0, 1) }}</text>
          </view>
          <view class="guardian__info">
            <view class="guardian__name-row">
              <text class="guardian__name">{{ guardian.name }}</text>
              <text v-if="guardian.relation" class="guardian__relation">
                {{ relationLabel(guardian.relation) }}
              </text>
            </view>
            <text class="guardian__email">{{ guardian.email }}</text>
          </view>
        </view>
        <view class="guardian__actions">
          <text class="guardian__action" @click="openEdit(guardian)">编辑</text>
          <text class="guardian__action guardian__action--danger" @click="askDelete(guardian)">删除</text>
        </view>
      </view>

      <button
        v-if="guardianStore.canAddMore"
        class="add-btn zm-btn-reset"
        hover-class="add-btn--pressed"
        @click="openCreate"
      >
        + 添加守护人
      </button>
      <text v-else class="limit-hint">已达上限，删除后可再添加</text>
    </view>

    <view class="notice">
      <text class="notice__text">
        提醒邮件只包含「长时间未确认」的时间信息，不包含定位、健康数据或聊天内容。
        你也可以随时删除守护人，删除后不再发送任何邮件。
      </text>
    </view>

    <!-- 表单 -->
    <view v-if="formVisible" class="sheet" @touchmove.stop.prevent>
      <view class="sheet__mask" @click="closeForm" />
      <view class="sheet__panel">
        <text class="sheet__title">{{ editingId ? '编辑守护人' : '添加守护人' }}</text>

        <view class="field">
          <text class="field__label">称呼</text>
          <input
            v-model="form.name"
            class="field__input"
            type="text"
            maxlength="32"
            placeholder="例如：妈妈"
            placeholder-class="field__placeholder"
            :cursor-spacing="24"
          />
          <text v-if="fieldErrors.name" class="field__error">{{ fieldErrors.name }}</text>
        </view>

        <view class="field">
          <text class="field__label">邮箱</text>
          <input
            v-model="form.email"
            class="field__input"
            type="text"
            maxlength="254"
            placeholder="name@example.com"
            placeholder-class="field__placeholder"
            :cursor-spacing="24"
          />
          <text v-if="fieldErrors.email" class="field__error">{{ fieldErrors.email }}</text>
        </view>

        <view class="field">
          <text class="field__label">关系（可选）</text>
          <view class="chips">
            <view
              v-for="option in relationOptions"
              :key="option.value"
              class="chips__item"
              :class="{ 'chips__item--active': form.relation === option.value }"
              @click="toggleRelation(option.value)"
            >
              {{ option.label }}
            </view>
          </view>
        </view>

        <text v-if="formError" class="form-error">{{ formError }}</text>

        <view class="sheet__actions">
          <button class="sheet__btn sheet__btn--ghost zm-btn-reset" @click="closeForm">取消</button>
          <button
            class="sheet__btn sheet__btn--primary zm-btn-reset"
            :disabled="submitting"
            @click="submit"
          >
            {{ submitting ? '保存中…' : '保存' }}
          </button>
        </view>
      </view>
    </view>

    <ConfirmDialog
      v-model="deleteVisible"
      title="删除守护人"
      :content="deleteContent"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import NavBar from '@/components/NavBar.vue'
import StateView from '@/components/StateView.vue'
import { ApiError, humanizeError } from '@/api/http'
import type { Guardian } from '@/api/types'
import { useGuardianStore } from '@/stores/guardians'
import { hasErrors, validateGuardian, type FieldErrors } from '@/utils/validate'

const guardianStore = useGuardianStore()

const relationOptions = [
  { value: 'family', label: '家人' },
  { value: 'friend', label: '朋友' },
  { value: 'partner', label: '伴侣' },
  { value: 'colleague', label: '同事' },
  { value: 'other', label: '其他' }
]

const formVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formError = ref('')
const fieldErrors = reactive<FieldErrors>({})

const form = reactive({
  name: '',
  email: '',
  relation: ''
})

const deleteVisible = ref(false)
const deleting = ref(false)
const deleteTarget = ref<Guardian | null>(null)

const deleteContent = computed(() =>
  deleteTarget.value
    ? `删除后，${deleteTarget.value.name} 将不再收到任何提醒邮件。`
    : ''
)

function relationLabel(value: string): string {
  return relationOptions.find((item) => item.value === value)?.label || '其他'
}

function resetForm(): void {
  form.name = ''
  form.email = ''
  form.relation = ''
  formError.value = ''
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])
}

function openCreate(): void {
  if (!guardianStore.canAddMore) {
    uni.showToast({ title: '最多 3 位守护人', icon: 'none' })
    return
  }
  resetForm()
  editingId.value = null
  formVisible.value = true
}

function openEdit(guardian: Guardian): void {
  resetForm()
  editingId.value = guardian.id
  form.name = guardian.name
  form.email = guardian.email
  form.relation = guardian.relation || ''
  formVisible.value = true
}

function closeForm(): void {
  if (submitting.value) return
  formVisible.value = false
}

function toggleRelation(value: string): void {
  form.relation = form.relation === value ? '' : value
}

async function submit(): Promise<void> {
  if (submitting.value) return
  formError.value = ''
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])

  const errors = validateGuardian({ name: form.name, email: form.email })
  if (hasErrors(errors)) {
    Object.assign(fieldErrors, errors)
    return
  }

  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      email: form.email.trim().toLowerCase(),
      relation: form.relation || null
    }
    if (editingId.value) {
      await guardianStore.edit(editingId.value, payload)
    } else {
      await guardianStore.add(payload)
    }
    formVisible.value = false
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.code === 'GUARDIAN_EMAIL_DUPLICATE') {
        fieldErrors.email = '这个邮箱已经在列表里了'
      } else if (err.code === 'GUARDIAN_LIMIT') {
        formError.value = '最多只能添加 3 位守护人'
      } else {
        formError.value = err.message
      }
    } else {
      formError.value = humanizeError(err)
    }
  } finally {
    submitting.value = false
  }
}

function askDelete(guardian: Guardian): void {
  deleteTarget.value = guardian
  deleteVisible.value = true
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    await guardianStore.remove(deleteTarget.value.id)
    deleteVisible.value = false
    uni.showToast({ title: '已删除', icon: 'success' })
  } catch (err) {
    uni.showToast({ title: humanizeError(err), icon: 'none' })
  } finally {
    deleting.value = false
  }
}

function reload(): void {
  void guardianStore.load(true)
}

onLoad(() => {
  void guardianStore.load(true)
})
</script>

<style scoped lang="scss">
.intro {
  margin-top: $zm-space-md;
  display: flex;
  flex-direction: column;

  &__title {
    font-size: $zm-font-lg;
    font-weight: 600;
    color: $zm-text;
  }

  &__text {
    margin-top: 8rpx;
    font-size: $zm-font-sm;
    line-height: 1.7;
    color: $zm-text-muted;
  }
}

.counter {
  margin: $zm-space-lg 0 $zm-space-sm;
  display: flex;
  align-items: baseline;

  &__text {
    font-size: $zm-font-sm;
    color: $zm-text-secondary;
  }

  &__hint {
    margin-left: $zm-space-xs;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }
}

.list {
  display: flex;
  flex-direction: column;
}

.guardian {
  background-color: $zm-surface;
  border-radius: $zm-radius-lg;
  padding: $zm-space-lg;
  border: 1rpx solid $zm-border;
  margin-bottom: $zm-space-sm;

  &__main {
    display: flex;
    align-items: center;
  }

  &__avatar {
    width: 80rpx;
    height: 80rpx;
    border-radius: 50%;
    background-color: $zm-primary-soft;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: $zm-space-md;
  }

  &__avatar-text {
    font-size: 32rpx;
    font-weight: 600;
    color: $zm-primary-dark;
  }

  &__info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  &__name-row {
    display: flex;
    align-items: center;
  }

  &__name {
    font-size: $zm-font-md;
    font-weight: 600;
    color: $zm-text;
  }

  &__relation {
    margin-left: 12rpx;
    font-size: 20rpx;
    color: $zm-text-secondary;
    background-color: $zm-surface-alt;
    padding: 4rpx 14rpx;
    border-radius: $zm-radius-pill;
  }

  &__email {
    margin-top: 4rpx;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__actions {
    margin-top: $zm-space-md;
    padding-top: $zm-space-md;
    border-top: 1rpx solid $zm-border;
    display: flex;
    justify-content: flex-end;
  }

  &__action {
    margin-left: $zm-space-lg;
    font-size: $zm-font-sm;
    color: $zm-text-secondary;

    &--danger {
      color: $zm-danger;
    }
  }
}

.add-btn {
  margin-top: $zm-space-sm;
  padding: 28rpx 0;
  text-align: center;
  font-size: $zm-font-md;
  color: $zm-primary-dark;
  background-color: $zm-primary-soft;
  border-radius: $zm-radius-lg;

  &--pressed {
    opacity: 0.8;
  }
}

.limit-hint {
  display: block;
  text-align: center;
  padding: $zm-space-md 0;
  font-size: $zm-font-xs;
  color: $zm-text-muted;
}

.notice {
  margin-top: $zm-space-lg;
  padding: $zm-space-md $zm-space-lg;
  border-radius: $zm-radius-md;
  background-color: $zm-surface-alt;
  border: 1rpx solid $zm-border;

  &__text {
    font-size: $zm-font-xs;
    line-height: 1.8;
    color: $zm-text-secondary;
  }
}

.sheet {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: flex-end;

  &__mask {
    position: absolute;
    inset: 0;
    background-color: rgba(20, 23, 28, 0.42);
  }

  &__panel {
    position: relative;
    width: 100%;
    background-color: $zm-surface;
    border-top-left-radius: $zm-radius-lg;
    border-top-right-radius: $zm-radius-lg;
    padding: $zm-space-lg $zm-space-lg calc(#{$zm-space-lg} + env(safe-area-inset-bottom));
    animation: zm-sheet-in 0.2s ease-out;
  }

  &__title {
    display: block;
    font-size: $zm-font-lg;
    font-weight: 600;
    color: $zm-text;
    text-align: center;
    margin-bottom: $zm-space-md;
  }

  &__actions {
    margin-top: $zm-space-lg;
    display: flex;
    gap: $zm-space-sm;
  }

  &__btn {
    flex: 1;
    height: 92rpx;
    line-height: 92rpx;
    text-align: center;
    border-radius: $zm-radius-md;
    font-size: $zm-font-md;

    &--ghost {
      background-color: $zm-surface-alt;
      color: $zm-text-secondary;
      border: 1rpx solid $zm-border;
    }

    &--primary {
      background-color: $zm-primary;
      color: $zm-text-inverse;
    }
  }
}

.field {
  margin-top: $zm-space-md;

  &__label {
    display: block;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
    margin-bottom: 10rpx;
  }

  &__input {
    height: 92rpx;
    background-color: $zm-surface-alt;
    border: 1rpx solid $zm-border;
    border-radius: $zm-radius-md;
    padding: 0 $zm-space-md;
    font-size: $zm-font-md;
    color: $zm-text;
  }

  &__placeholder {
    color: $zm-text-muted;
  }

  &__error {
    display: block;
    margin-top: 8rpx;
    font-size: $zm-font-xs;
    color: $zm-danger;
  }
}

.chips {
  display: flex;
  flex-wrap: wrap;

  &__item {
    padding: 12rpx 26rpx;
    margin: 0 12rpx 12rpx 0;
    border-radius: $zm-radius-pill;
    font-size: $zm-font-xs;
    color: $zm-text-secondary;
    background-color: $zm-surface-alt;
    border: 1rpx solid $zm-border;

    &--active {
      color: $zm-primary-dark;
      background-color: $zm-primary-soft;
      border-color: rgba(18, 184, 134, 0.4);
    }
  }
}

.form-error {
  display: block;
  margin-top: $zm-space-sm;
  font-size: $zm-font-xs;
  color: $zm-danger;
}

@keyframes zm-sheet-in {
  from {
    transform: translateY(40rpx);
    opacity: 0.6;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
