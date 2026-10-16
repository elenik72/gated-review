# NestJS Code Review Guide

> NestJS code review guide covering core topics: dependency injection and layered architecture, module organization, Guard/Interceptor/Pipe, DTO validation, error handling, circular dependencies, and testing patterns.

## Contents

- [Dependency Injection and Layered Architecture](#dependency-injection-and-layered-architecture)
- [Module Organization](#module-organization)
- [Guard / Interceptor / Pipe](#guard--interceptor--pipe)
- [Validation Patterns (DTO)](#validation-patterns-dto)
- [Error Handling](#error-handling)
- [Circular Dependencies](#circular-dependencies)
- [Testing Patterns](#testing-patterns)
- [Review Checklist](#review-checklist)

---

## Dependency Injection and Layered Architecture

### Three-Layer Architecture: Controller → Service → Repository

```typescript
// ❌ ORM injected directly into the Controller, skipping the Service layer
@Controller('users')
export class UsersController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  findAll() {
    return this.prisma.user.findMany();
  }
}

// ✅ Controller → Service → Repository
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  findAll() {
    return this.usersService.findAll();
  }
}

@Injectable()
export class UsersService {
  constructor(private readonly usersRepo: UsersRepository) {}

  findAll() {
    return this.usersRepo.findAll();
  }
}
```

### Repository Classes Should Not Inject Each Other

```typescript
// ❌ A Repository imports another Repository - orchestration logic belongs in the Service
@Injectable()
export class OrdersRepository {
  constructor(private readonly usersRepository: UsersRepository) {}
}

// ✅ Cross-Repository orchestration is done in the Service
@Injectable()
export class OrdersService {
  constructor(
    private readonly ordersRepo: OrdersRepository,
    private readonly usersRepo: UsersRepository,
  ) {}
}
```

### God Service: Split When It Has More Than 8 Dependencies

```typescript
// ❌ Giant Service with 9 dependencies
@Injectable()
export class OrdersService {
  constructor(
    private readonly ordersRepo: OrdersRepository,
    private readonly usersRepo: UsersRepository,
    private readonly productsRepo: ProductsRepository,
    private readonly paymentsService: PaymentsService,
    private readonly mailerService: MailerService,
    private readonly inventoryService: InventoryService,
    private readonly discountService: DiscountService,
    private readonly taxService: TaxService,
    private readonly auditService: AuditService,
  ) {}
}

// ✅ Split into Use-Case Service classes (one operation per file)
@Injectable()
export class CreateOrderService {
  constructor(
    private readonly ordersRepo: OrdersRepository,
    private readonly paymentsService: PaymentsService,
  ) {}

  async execute(dto: CreateOrderDto) { /* ... */ }
}
```

### Dependency Inversion with Symbol Token

```typescript
// ❌ Depends directly on the concrete implementation - cannot be replaced in tests
@Injectable()
export class UsersService {
  constructor(private readonly repo: TypeOrmUserRepository) {}
}

// ✅ Interface + Symbol Token - replaceable with an in-memory implementation
export const USER_REPOSITORY = Symbol('USER_REPOSITORY');

export interface UserRepository {
  findAll(): Promise<User[]>;
  findById(id: string): Promise<User | null>;
}

// module:
{
  provide: USER_REPOSITORY,
  useClass: TypeOrmUserRepository,
}

// service:
@Injectable()
export class UsersService {
  constructor(@Inject(USER_REPOSITORY) private readonly repo: UserRepository) {}
}
```

---

## Module Organization

### Recommended Four-Layer Structure

```
src/
  common/         ← Global technical infrastructure (Guards, Filters, Interceptors, Decorators)
  core/           ← Internal infrastructure (Config, Database, Queue configuration)
  integrations/   ← External service wrappers (Mailer, Storage, Stripe, SMS)
  modules/        ← Business logic organized by domain
    [feature]/
      dtos/
      repositories/
      services/
        internal/     ← Service classes shared within the module
        use-cases/    ← One file = one operation
      types/
      [feature].controller.ts
      [feature].module.ts
```

### Domain Must Be Framework-Agnostic

```typescript
// ❌ Domain Entity depends on NestJS - cannot be tested independently
import { Injectable } from '@nestjs/common';

@Injectable()
export class User {
  constructor(private readonly email: string) {}
}

// ✅ Domain is a plain class with no framework decorators
export class User {
  private constructor(private readonly email: string) {}

  static create(email: string): User {
    return new User(email);
  }
}
```

### Key Rules

- `common/` must **contain no business logic** - if it needs to know about "orders", it does not belong here
- `integrations/` wraps each external service; swapping SendGrid → AWS SES changes only one directory
- Prefer **Use-Case Service** (one operation per file) over a giant `XxxService` with 15 methods

---

## Guard / Interceptor / Pipe

### Business Logic Does Not Belong in a Guard

```typescript
// ❌ Database query + business checks inside a Guard
@Injectable()
export class OrderOwnershipGuard implements CanActivate {
  constructor(private readonly prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest();
    const order = await this.prisma.order.findUnique({
      where: { id: req.params.id },
    });
    if (order.userId !== req.user.id) {
      return false; // Data fetching + business-rule checks both live in the Guard
    }
    return true;
  }
}

// ✅ Guard only does authorization checks (roles/permissions)
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>('roles', [
      context.getHandler(),
      context.getClass(),
    ]);
    if (!requiredRoles) return true;
    const { user } = context.switchToHttp().getRequest();
    return requiredRoles.some((role) => user.roles?.includes(role));
  }
}
```

### Interceptor Is Only for Cross-Cutting Concerns

```typescript
// ❌ Business logic executed inside an Interceptor
@Injectable()
export class PricingInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler) {
    // Computing discounts - this is not a cross-cutting concern!
    return next.handle().pipe(map(data => applyDiscount(data)));
  }
}

// ✅ Interceptor is for logging, caching, response transformation, timing
@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler) {
    const now = Date.now();
    const req = context.switchToHttp().getRequest();
    return next.handle().pipe(
      tap(() => console.log(`${req.method} ${req.url} - ${Date.now() - now}ms`)),
    );
  }
}
```

### Global ValidationPipe Must Configure whitelist

```typescript
// ❌ No whitelist - extra properties in the request body pass straight through
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  await app.listen(3000);
}

// ✅ Global ValidationPipe + whitelist filters out unknown properties
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );
  await app.listen(3000);
}
```

---

## Validation Patterns (DTO)

### @ValidateNested() Must Be Paired with @Type()

```typescript
// ❌ @ValidateNested alone - nested object validation is silently skipped!
export class CreateOrderDto {
  @ValidateNested()
  shipping: AddressDto;
}

// ✅ @ValidateNested + @Type used together
import { Type } from 'class-transformer';

export class CreateOrderDto {
  @ValidateNested()
  @Type(() => AddressDto)
  shipping: AddressDto;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => OrderItemDto)
  items: OrderItemDto[];
}
```

### No Bare any Body

```typescript
// ❌ No DTO - no validation, no type safety, no Swagger docs
@Post()
create(@Body() body: any) {
  return this.service.create(body);
}

// ✅ Create a DTO for each operation
export class CreateUserDto {
  @IsEmail()
  email: string;

  @IsString()
  @MinLength(2)
  @MaxLength(100)
  name: string;
}

@Post()
create(@Body() dto: CreateUserDto) {
  return this.service.create(dto);
}
```

### Create and Update Should Use Different DTO Classes

```typescript
// ❌ PATCH also requires all fields - poor API design
@Patch(':id')
update(@Body() dto: CreateUserDto) { /* all fields required */ }

// ✅ Update uses PartialType
export class UpdateUserDto extends PartialType(CreateUserDto) {}

@Patch(':id')
update(@Body() dto: UpdateUserDto) { /* all fields optional */ }
```

### Optional Nested Objects

```typescript
// ❌ Optional nested object is missing @IsOptional
export class UpdateOrderDto {
  @ValidateNested()
  @Type(() => AddressDto)
  shipping?: AddressDto; // Still validated when undefined
}

// ✅ @IsOptional + @ValidateNested + @Type
export class UpdateOrderDto {
  @IsOptional()
  @ValidateNested()
  @Type(() => AddressDto)
  shipping?: AddressDto;
}
```

---

## Error Handling

### Do Not Swallow Errors

```typescript
// ❌ catch { return null } - hides the problem; callers cannot tell "not found" from "failed"
async findOne(id: string) {
  try {
    return await this.repo.findById(id);
  } catch (e) {
    return null;
  }
}

// ✅ Throw a meaningful exception
async findOne(id: string): Promise<User> {
  const user = await this.repo.findById(id);
  if (!user) {
    throw new NotFoundException(`User ${id} not found`);
  }
  return user;
}
```

### Use Built-in Exception Classes

```typescript
// ❌ Manually building an HTTP response
throw new HttpException('Bad request', 400);

// ✅ Use semantic built-in exceptions
throw new BadRequestException('Invalid email format');
throw new NotFoundException('User not found');
throw new ConflictException('Email already taken');
throw new ForbiddenException('Insufficient permissions');
throw new UnauthorizedException('Invalid credentials');
```

### Custom Exception Filters

```typescript
// ✅ Global exception filter - uniform response format
@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse();
    const request = ctx.getRequest();

    const status =
      exception instanceof HttpException
        ? exception.getStatus()
        : HttpStatus.INTERNAL_SERVER_ERROR;

    this.logger.error(`${request.method} ${request.url} - ${status}`, exception instanceof Error ? exception.stack : '');

    response.status(status).json({
      statusCode: status,
      timestamp: new Date().toISOString(),
      path: request.url,
    });
  }
}
```

---

## Circular Dependencies

### Circular Dependencies Between Modules

```typescript
// ❌ Module A ↔ Module B
@Module({ imports: [UsersModule] })
export class OrdersModule {}

@Module({ imports: [OrdersModule] })
export class UsersModule {}

// ✅ Extract shared logic into a third module
@Module({
  providers: [SharedService],
  exports: [SharedService],
})
export class SharedModule {}

@Module({ imports: [SharedModule] })
export class OrdersModule {}

@Module({ imports: [SharedModule] })
export class UsersModule {}
```

### forwardRef Is the Last Resort

```typescript
// ⚠️ forwardRef signals a design problem - redesign first
@Module({
  imports: [forwardRef(() => UsersModule)],
})
export class OrdersModule {}

// ✅ Redesign to remove the cycle:
// 1. Extract a shared module
// 2. Use event-driven communication (EventEmitter) instead of direct calls
// 3. Move shared logic up into a higher-level Service
```

---

## Testing Patterns

### Use-Case Classes Can Be Tested Without NestJS

```typescript
// ✅ No NestFactory needed - instantiate directly with new
describe('CreateUserHandler', () => {
  let handler: CreateUserHandler;
  let repo: InMemoryUserRepository;

  beforeEach(() => {
    repo = new InMemoryUserRepository();
    handler = new CreateUserHandler(repo);
  });

  it('creates a user', async () => {
    const id = await handler.execute(
      new CreateUserCommand('user@example.com', 'Alice'),
    );
    expect(id).toBeDefined();
  });

  it('rejects duplicate email', async () => {
    await handler.execute(new CreateUserCommand('user@example.com', 'Alice'));
    await expect(
      handler.execute(new CreateUserCommand('user@example.com', 'Bob')),
    ).rejects.toThrow('already exists');
  });
});
```

### E2E Tests Should Configure the Same Pipes as Production

```typescript
describe('UsersController (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    // Must be the same global config as in main.ts
    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true,
      }),
    );
    await app.init();
  });

  it('/POST users - valid', () => {
    return request(app.getHttpServer())
      .post('/users')
      .send({ email: 'test@test.com', name: 'Test' })
      .expect(201);
  });

  it('/POST users - extra fields rejected', () => {
    return request(app.getHttpServer())
      .post('/users')
      .send({ email: 'test@test.com', name: 'Test', role: 'admin' })
      .expect(400);
  });
});
```

---

## Review Checklist

### Layered Architecture

- [ ] ORM/Prisma is not injected directly into the Controller
- [ ] No business logic in the Controller
- [ ] No Repository-to-Repository injection
- [ ] Service dependency count ≤ 8 (split into Use-Case classes if exceeded)

### Dependency Injection

- [ ] Interface + Symbol Token used for replaceable dependencies
- [ ] No `forwardRef()` (if present, a design document must explain why)
- [ ] No Scoped service injected into a Singleton

### Validation

- [ ] Every `@ValidateNested()` has a matching `@Type()`
- [ ] Global `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })` is configured
- [ ] No `@Body() body: any` - a DTO is required
- [ ] Create and Update use different DTO classes (`PartialType`)
- [ ] Array validation uses `{ each: true }`
- [ ] Optional nested objects use `@IsOptional()` + `@ValidateNested()` + `@Type()`

### Guard / Interceptor / Pipe

- [ ] Guard only does authorization checks and does not query the database
- [ ] Interceptor is used only for cross-cutting concerns (logging, caching, response transformation)
- [ ] Business rules live in the Service

### Error Handling

- [ ] No `catch { return null }` - throw a meaningful exception
- [ ] Use NestJS built-in exception classes
- [ ] Custom exception filters live in `common/filters/`

### Modules

- [ ] No circular module imports
- [ ] Domain Entity has no framework decorators (`@Injectable`, etc.)
- [ ] External service calls live in `integrations/`

### Testing

- [ ] Use-Case Service can be tested without NestJS
- [ ] E2E tests configure the same global Pipes/Guards as production
- [ ] Domain Entity has zero framework dependencies
