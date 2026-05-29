
### 1. Модели бизнес-процессов (BPMN/Потоки работ)

#### Модель «AS-IS» (Текущее состояние)
```mermaid
graph TD
    subgraph "Магазин / Менеджер"
        A1[Проверка остатков на полках] --> A2[Анализ продаж на основе интуиции]
        A2 --> A3{Формирование заказа}
        A3 -->|Риск ошибки| A4[Создание заявки в ERP вручную]
    end

    subgraph "Логистика / Склад"
        A4 --> A5[Комплектация товара]
        A5 --> A6[Доставка в магазин]
    end

    subgraph "Результат"
        A6 --> R1[Избыток: Списание/Просрочка]
        A6 --> R2[Дефицит: Упущенная выручка]
    end

    style A2 fill:#f96,stroke:#333
    style R1 fill:#ff9999
    style R2 fill:#ff9999
```
**Описание:** Отражает текущий ручной процесс. Основной акцент сделан на «интуитивном анализе», который является источником ошибок (избытка или дефицита товара) и прямых финансовых потерь.

#### Модель «TO-BE» (Целевое состояние)
```mermaid
graph TD
    subgraph "Data Pipeline (Инфраструктура)"
        B1[(БД Продаж: 2.6 млрд строк)] --> B2[Data Engineer: Сбор и очистка данных]
        B2 --> B3[AI-модель: Прогнозирование спроса]
    end

    subgraph "Автоматизированная система"
        B3 --> B4[Генерация автозаказа на каждую точку]
        B4 --> B5{Система контроля}
    end

    subgraph "Магазин / Менеджер"
        B5 -->|Авто-подтверждение| B6[Валидация аномалий менеджером]
        B6 --> B7[Финальный заказ отправлен]
    end

    subgraph "Логистика / Склад"
        B7 --> B8[Оптимизированная отгрузка]
    end

    subgraph "Результат"
        B8 --> R3[Минимизация списаний]
        B8 --> R4[Максимальное наличие товара]
        B8 --> R5[Рост выручки]
    end

    style B3 fill:#bbf,stroke:#333
    style B4 fill:#bbf,stroke:#333
    style R3 fill:#99ff99
    style R4 fill:#99ff99
    style R5 fill:#99ff99
```
**Описание:** Демонстрирует автоматизацию аналитического блока. ИИ заменяет интуицию менеджера, перекладывая рутину на систему и оставляя человеку только функцию контроля аномалий.

---

### 2. Диаграмма структуры данных (ER-диаграмма)

```mermaid
erDiagram
    FACT_SALES {
        Int64 sale_id PK
        DateTime timestamp
        Int32 store_id FK
        Int32 product_id FK
        Float32 quantity
        Float32 price
        UInt8 is_promo
    }

    FACT_FORECAST {
        Int64 forecast_id PK
        Date target_date
        Int32 store_id FK
        Int32 product_id FK
        Float32 predicted_quantity
        Float32 confidence_interval
        DateTime generated_at
    }

    DIM_PRODUCTS {
        Int32 product_id PK
        String name
        String category
        Int16 shelf_life_days
        Float32 cost_price
    }

    DIM_STORES {
        Int32 store_id PK
        String city
        String address
        String store_format
    }

    DIM_CALENDAR {
        Date date PK
        UInt8 day_of_week
        UInt8 is_holiday
        String event_name
    }

    FACT_SALES }o--|| DIM_STORES : "продано в"
    FACT_SALES }o--|| DIM_PRODUCTS : "содержит"
    FACT_SALES }o--|| DIM_CALENDAR : "дата"
    FACT_FORECAST }o--|| DIM_STORES : "для магазина"
    FACT_FORECAST }o--|| DIM_PRODUCTS : "для товара"
```
**Описание:** Схема типа «Снежинка» (Snowflake Schema) для OLAP-системы. Разделяет быстрорастущие факты (2.6 млрд транзакций) и справочники (Dimensions), обеспечивая высокую скорость аналитических запросов и обучения моделей.

---

### 3. Диаграмма архитектуры распределенной системы

```mermaid
graph TD
    subgraph "Уровень источников (500 магазинов)"
        S1[Магазин 1: POS-терминал]
        S2[Магазин 2: POS-терминал]
        S3[Магазин N: POS-терминал]
    end

    subgraph "Уровень сбора данных (Ingestion)"
        Kafka{Apache Kafka / Message Broker}
        S1 --> Kafka
        S2 --> Kafka
        S3 --> Kafka
    end

    subgraph "Распределенное хранилище (Data Lake / Warehouse)"
        direction LR
        Node1[(Shard 1: Магазины 1-100)]
        Node2[(Shard 2: Магазины 101-200)]
        Node3[(Shard 3: Магазины 201-500)]
        Kafka --> Node1
        Kafka --> Node2
        Kafka --> Node3
    end

    subgraph "Распределенные вычисления (Compute Layer)"
        Spark[Apache Spark / Cluster]
        Node1 --- Spark
        Node2 --- Spark
        Node3 --- Spark
        ML[Обучение ИИ-моделей] <--> Spark
    end

    subgraph "Потребители (Serving Layer)"
        API[API Прогнозирования]
        Dashboard[Дашборд Менеджера]
        ERP[ERP Система заказов]
        ML --> API
        API --> Dashboard
        API --> ERP
    end

    style Node1 fill:#f9f,stroke:#333
    style Node2 fill:#f9f,stroke:#333
    style Node3 fill:#f9f,stroke:#333
    style Spark fill:#bbf,stroke:#333
```
**Описание:** Показывает распределение данных (шардирование по магазинам) и вычислений (Spark кластер). Это необходимо для параллельной обработки миллиардов строк и обеспечения отказоустойчивости при сбоях отдельных узлов.

---

### 4. Структурные UML-диаграммы

#### UML-диаграмма компонентов
```mermaid 
graph TD
    subgraph Data_Layer [Data Layer]
        IS[Ingestion Service]
        DB[(ClickHouse Cluster)]
    end

    subgraph AI_Service_Layer [AI Service Layer]
        FS[Feature Store]
        ML[ML Engine]
        IAPI[Inference API]
    end

    subgraph Application_Layer [Application Layer]
        UI[Admin Dashboard]
        ERP[ERP Connector]
    end

    POS[External POS Systems] -->|JSON Stream| IS
    IS -->|Batch Write| DB
    DB -->|Historical Data| FS
    FS -->|Features| ML
    ML -->|Model Artifacts| IAPI
    IAPI -->|REST API| UI
    IAPI -->|XML/JSON| ERP

    style DB fill:#f9f,stroke:#333,stroke-width:2px
    style ML fill:#bbf,stroke:#333,stroke-width:2px
    style IAPI fill:#bfb,stroke:#333,stroke-width:2px
```
**Описание:** Описывает логическую структуру системы. Разделение на независимые слои (Data, AI, App) позволяет обновлять модели ИИ (ML Engine) без остановки интерфейса пользователя (UI).

#### UML-диаграмма классов
```mermaid 
classDiagram
    class Store {
        +int store_id
        +string city
        +get_inventory_limits()
    }

    class Product {
        +int product_id
        +string name
        +int shelf_life_days
        +is_perishable() bool
    }

    class Transaction {
        +long transaction_id
        +datetime sale_time
        +float quantity
    }

    class ForecastModel {
        +string model_version
        +predict(store_id, product_id) ForecastResult
    }

    class ForecastResult {
        +date target_date
        +float predicted_value
        +float confidence_score
    }

    Store "1" --o "*" Transaction
    Product "1" --o "*" Transaction
    ForecastModel ..> ForecastResult
    ForecastResult "*" --o "1" Store
    ForecastResult "*" --o "1" Product
```
**Описание:** Статическая структура кода. Описывает сущности магазина, товара и транзакции, а также логику взаимодействия модели прогнозирования с результатами.

---

### 5. Поведенческие UML-диаграммы

#### Диаграмма прецедентов (Use Case)
```mermaid 
graph LR
    Manager((Менеджер магазина))
    AI_System((Система ИИ))
    Admin((Администратор))

    subgraph "IS"
        UC1(Просмотр прогноза спроса)
        UC2(Корректировка автозаказа)
        UC3(Подтверждение поставки)
        UC4(Мониторинг точности)
        UC5(Переобучение моделей)
    end

    Manager --> UC1
    Manager --> UC2
    Manager --> UC3
    AI_System --> UC1
    AI_System --> UC5
    Admin --> UC4
    Admin --> UC5
```
**Описание:** Описывает функциональные возможности системы для разных ролей: менеджера, самой системы ИИ (автономные действия) и администратора.

#### Диаграмма последовательности (Sequence Diagram)
```mermaid
sequenceDiagram
    autonumber
    participant Sch as Планировщик
    participant DB as ClickHouse
    participant ML as ML-сервис
    participant UI as Интерфейс
    participant ERP as ERP-система

    Sch->>DB: Запрос продаж за 365 дней
    DB-->>Sch: Данные по 10 000 товарам
    Sch->>ML: Передача признаков
    ML->>ML: Расчет прогноза
    ML-->>Sch: Результат на +7 дней
    Sch->>DB: Сохранение прогноза
    UI->>DB: Загрузка черновика заказа
    DB-->>UI: Прогноз
    UI->>UI: Валидация менеджером
    UI->>ERP: Заказ отправлен
```
**Описание:** Отражает динамику работы системы во времени: от ночного сбора данных и работы ML-сервиса до утреннего подтверждения заказа менеджером.

#### Диаграмма активностей (Activity Diagram)
```mermaid 
graph TD
    Start([Начало цикла]) --> Fetch[Сбор остатков]
    Fetch --> AI_Calc[Расчет прогноза]
    AI_Calc --> Check{Аномальный спрос?}
    
    Check -- Да --> Alert[Алерт менеджеру]
    Alert --> Manual[Ручная правка]
    
    Check -- Нет --> Auto[Автозаказ]
    
    Manual --> Submit[Отправка заказа]
    Auto --> Submit
    Submit --> End([Конец])

    style Check fill:#fff4dd,stroke:#d4a017
```
**Описание:** Алгоритм принятия решения в системе. Акцентирует внимание на блоке «аномального спроса», где система запрашивает вмешательство человека для снижения рисков.
