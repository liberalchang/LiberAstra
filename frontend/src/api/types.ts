/**
 * 与后端 FastAPI 自动生成的 OpenAPI 类型对应（M0 手写，后续可用 openapi-typescript 生成）。
 */
export interface components {
  schemas: {
    AuthStatus: { initialized: boolean };
    UserOut: { id: number; username: string; is_admin: boolean; created_at: string };
    TokenResponse: { access_token: string; token_type: string };
  };
}
