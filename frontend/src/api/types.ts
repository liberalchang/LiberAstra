/**
 * 与后端 FastAPI 自动生成的 OpenAPI 类型对应（手写维护，后续可用 openapi-typescript 生成）。
 */
export interface components {
  schemas: {
    AuthStatus: { initialized: boolean };
    UserOut: { id: number; username: string; is_admin: boolean; created_at: string };
    TokenResponse: { access_token: string; token_type: string };
    ModelParamField: {
      key: string;
      type: string;
      label: string;
      default?: string | number | boolean | null;
      options?: string[] | null;
      min?: number | null;
      max?: number | null;
      when_sub?: string;
    };
    ProviderTypeInfo: {
      type: string;
      label: string;
      capabilities: string[];
      requires_api_key: boolean;
      default_base_url: string | null;
      description: string;
      group?: string;
      model_kinds?: string[];
      sub_capabilities_by_kind?: Record<string, string[]>;
      param_schemas?: Record<string, components["schemas"]["ModelParamField"][]>;
    };
    CapabilitiesOut: { provider_types: components["schemas"]["ProviderTypeInfo"][]; capabilities: string[] };
    ProviderOut: {
      id: number;
      name: string;
      type: string;
      base_url: string;
      has_api_key: boolean;
      models: string[];
      capabilities: string[];
      concurrency: number;
      enabled: boolean;
      extra: Record<string, unknown>;
      created_at: string;
      updated_at: string;
    };
    TestResult: { ok: boolean; message: string };
  };
}
