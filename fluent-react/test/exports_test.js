import assert from 'assert';
import * as FluentReact from '../src/index';
import LocalizationProvider from '../src/provider';
import Localized from '../src/localized';
import withLocalization from '../src/with_localization';
import ReactLocalization, { isReactLocalization } from '../src/localization';

suite('Exports', () => {
  test('LocalizationProvider', () => {
    assert.strictEqual(FluentReact.LocalizationProvider, LocalizationProvider);
  });

  test('Localized', () => {
    assert.strictEqual(FluentReact.Localized, Localized);
  });

  test('withLocalization', () => {
    assert.strictEqual(FluentReact.withLocalization, withLocalization);
  });

  test('ReactLocalization', () => {
    assert.strictEqual(FluentReact.ReactLocalization, ReactLocalization);
  });

  test('isReactLocalization', () => {
    assert.strictEqual(FluentReact.isReactLocalization, isReactLocalization);
  });
});
