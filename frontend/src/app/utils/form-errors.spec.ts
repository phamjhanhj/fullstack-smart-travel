import { FormControl, FormGroup, Validators } from '@angular/forms';
import { apiErrorMessage, applyApiErrors, controlErrorMessage, integerValidator, nonBlankValidator, timeRangeValidator } from './form-errors';

describe('form error helpers', () => {
  it('maps structured API errors to the matching control', () => {
    const form = new FormGroup({ title: new FormControl('') });
    const error = { error: { message: 'Sai', data: { errors: [{ field: 'title', code: 'x', message: 'Tiêu đề quá ngắn.' }] } } };

    expect(applyApiErrors(form, error, 'Lỗi')).toBe('Tiêu đề quá ngắn.');
    expect(form.get('title')?.errors?.['server']).toBe('Tiêu đề quá ngắn.');
  });

  it('creates a readable local validation message', () => {
    const control = new FormControl('', [Validators.required]);
    control.markAsTouched();
    expect(controlErrorMessage(control, 'Tên chuyến đi')).toBe('Tên chuyến đi là bắt buộc.');
  });

  it('rejects an end time before the start time', () => {
    const form = new FormGroup(
      { start_time: new FormControl('09:00'), end_time: new FormControl('08:00') },
      { validators: timeRangeValidator() },
    );
    expect(form.hasError('timeRange')).toBeTrue();
    expect(form.get('end_time')?.hasError('timeRange')).toBeTrue();

    form.get('end_time')?.setValue('10:00');
    expect(form.hasError('timeRange')).toBeFalse();
    expect(form.get('end_time')?.hasError('timeRange')).toBeFalse();
  });

  it('uses the API response message when there is no field issue', () => {
    expect(apiErrorMessage({ error: { message: 'Bạn không có quyền.' } }, 'Lỗi')).toBe('Bạn không có quyền.');
  });

  it('rejects whitespace-only required text', () => {
    const control = new FormControl('   ', [nonBlankValidator()]);
    expect(control.hasError('required')).toBeTrue();
    control.setValue('Hà Nội');
    expect(control.valid).toBeTrue();
  });

  it('rejects decimal values for integer API fields', () => {
    const control = new FormControl(1.5, [integerValidator()]);
    expect(control.hasError('integer')).toBeTrue();
    control.setValue(2);
    expect(control.valid).toBeTrue();
  });
});
