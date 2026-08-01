import { AbstractControl, FormGroup, ValidationErrors, ValidatorFn } from '@angular/forms';

export interface ApiValidationIssue {
  field: string | null;
  code: string;
  message: string;
}

const DEFAULT_MESSAGES: Record<string, string> = {
  required: 'Trường này là bắt buộc.',
  email: 'Email không đúng định dạng.',
  pattern: 'Giá trị không đúng định dạng.',
  min: 'Giá trị nhỏ hơn mức tối thiểu.',
  max: 'Giá trị vượt quá mức tối đa.',
  minlength: 'Nội dung quá ngắn.',
  maxlength: 'Nội dung quá dài.',
  integer: 'Giá trị phải là số nguyên.',
  timeRange: 'Giờ kết thúc phải sau giờ bắt đầu.',
};

export function apiValidationIssues(error: unknown): ApiValidationIssue[] {
  const response = error as any;
  const issues = response?.error?.data?.errors;
  if (Array.isArray(issues)) {
    return issues.filter((item: any) => typeof item?.message === 'string');
  }
  const legacy = response?.error?.data?.detail || response?.error?.detail;
  if (!Array.isArray(legacy)) return [];
  return legacy.map((item: any) => ({
    field: String(item?.loc?.[item.loc.length - 1] || '') || null,
    code: String(item?.type || 'validation_error'),
    message: String(item?.msg || 'Dữ liệu không hợp lệ.'),
  }));
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  const firstIssue = apiValidationIssues(error)[0];
  const responseMessage = (error as any)?.error?.message;
  if (firstIssue?.message) return firstIssue.message;
  if (responseMessage && responseMessage !== 'Validation error') return responseMessage;
  return fallback;
}

export function applyApiErrors(form: FormGroup, error: unknown, fallback: string): string {
  const issues = apiValidationIssues(error);
  for (const issue of issues) {
    if (!issue.field) continue;
    const control = form.get(issue.field);
    if (!control) continue;
    control.setErrors({ ...control.errors, server: issue.message });
    control.markAsTouched();
  }
  return apiErrorMessage(error, fallback);
}

export function controlErrorMessage(
  control: AbstractControl | null | undefined,
  label: string,
  overrides: Partial<Record<string, string>> = {},
): string {
  if (!control?.errors) return '';
  if (typeof control.errors['server'] === 'string') return control.errors['server'];
  if (control.errors['required']) return `${label} là bắt buộc.`;
  if (control.errors['minlength']) {
    return `${label} phải có ít nhất ${control.errors['minlength'].requiredLength} ký tự.`;
  }
  if (control.errors['maxlength']) {
    return `${label} không được vượt quá ${control.errors['maxlength'].requiredLength} ký tự.`;
  }
  if (control.errors['min']) return `${label} phải từ ${control.errors['min'].min} trở lên.`;
  if (control.errors['max']) return `${label} không được lớn hơn ${control.errors['max'].max}.`;
  const key = Object.keys(control.errors)[0];
  return overrides[key] || DEFAULT_MESSAGES[key] || `${label} không hợp lệ.`;
}

export function timeRangeValidator(startField = 'start_time', endField = 'end_time'): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const start = control.get(startField)?.value;
    const end = control.get(endField)?.value;
    const endControl = control.get(endField);
    const isInvalid = !!start && !!end && end <= start;
    const currentErrors = endControl?.errors || {};

    if (isInvalid) {
      if (!currentErrors['timeRange']) {
        endControl?.setErrors({ ...currentErrors, timeRange: true });
      }
      return { timeRange: true };
    }

    if (currentErrors['timeRange']) {
      const { timeRange: _removed, ...remainingErrors } = currentErrors;
      endControl?.setErrors(Object.keys(remainingErrors).length ? remainingErrors : null);
    }
    return null;
  };
}

export function nonBlankValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = control.value;
    return typeof value === 'string' && value.trim().length === 0 ? { required: true } : null;
  };
}

export function integerValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = control.value;
    if (value === null || value === undefined || value === '') return null;
    return Number.isInteger(Number(value)) ? null : { integer: true };
  };
}
