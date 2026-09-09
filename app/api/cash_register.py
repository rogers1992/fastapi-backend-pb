from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal
from typing import List
from ..database import get_db
from ..models.cash_register import CashRegister, CashSession, CashMovement, CashRegisterStatus, MovementType
from ..models.sale import Sale
from ..models.user import User
from ..models.inventory import Warehouse
from ..schemas.cash_register import (
    CashRegisterCreate, CashRegisterUpdate, CashRegisterResponse,
    CashMovementCreate, CashMovementResponse,
    CashSessionOpen, CashSessionClose, CashSessionResponse, CashSessionSummary,
    WarehouseCajaSummary,
)
from ..core.dependencies import get_current_user, require_permission, require_role

router = APIRouter()


def _get_user_warehouse_ids(user: User) -> List[int]:
    return [w.id for w in user.warehouses] if user.warehouses else []


def _get_open_session_for_warehouse(db: Session, warehouse_id: int) -> CashSession | None:
    """Find any open session for a given warehouse (via register)."""
    return db.query(CashSession).options(
        selectinload(CashSession.movements)
    ).join(
        CashRegister, CashSession.register_id == CashRegister.id
    ).filter(
        CashRegister.warehouse_id == warehouse_id,
        CashSession.status == CashRegisterStatus.open,
    ).first()


def _compute_session_totals(db: Session, session: CashSession) -> dict:
    cash_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.cash_session_id == session.id,
        Sale.payment_method == 'efectivo'
    ).scalar()
    
    total_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.cash_session_id == session.id
    ).scalar()
    
    sales_count = db.query(func.count(Sale.id)).filter(
        Sale.cash_session_id == session.id
    ).scalar()
    
    total_in = db.query(func.coalesce(func.sum(CashMovement.amount), 0)).filter(
        CashMovement.session_id == session.id,
        CashMovement.type == MovementType.ingreso
    ).scalar()
    
    total_out = db.query(func.coalesce(func.sum(CashMovement.amount), 0)).filter(
        CashMovement.session_id == session.id,
        CashMovement.type == MovementType.egreso
    ).scalar()
    
    expected = Decimal(str(session.opening_amount)) + Decimal(str(cash_sales)) + Decimal(str(total_in)) - Decimal(str(total_out))
    
    sales_by_payment = {}
    payment_rows = db.query(Sale.payment_method, func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.cash_session_id == session.id
    ).group_by(Sale.payment_method).all()
    
    for method, total in payment_rows:
        sales_by_payment[method] = float(total)
    
    return {
        'cash_sales_total': Decimal(str(cash_sales)),
        'sales_total': Decimal(str(total_sales)),
        'sales_count': sales_count,
        'expected_amount': expected,
        'total_movements_in': Decimal(str(total_in)),
        'total_movements_out': Decimal(str(total_out)),
        'sales_by_payment': sales_by_payment,
    }


def _enrich_session_response(db: Session, session: CashSession) -> CashSessionResponse:
    totals = _compute_session_totals(db, session)
    
    register = db.query(CashRegister).filter(CashRegister.id == session.register_id).first()
    warehouse_id = register.warehouse_id if register else None
    warehouse_name = None
    if warehouse_id:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        warehouse_name = wh.name if wh else None
    
    return CashSessionResponse(
        id=session.id,
        register_id=session.register_id,
        warehouse_id=warehouse_id,
        warehouse_name=warehouse_name,
        user_id=session.user_id,
        opening_amount=session.opening_amount,
        closing_amount=session.closing_amount,
        expected_amount=totals['expected_amount'] if session.status == CashRegisterStatus.open else session.expected_amount,
        discrepancy=session.discrepancy,
        opening_notes=session.opening_notes,
        closing_notes=session.closing_notes,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        status=session.status.value if isinstance(session.status, CashRegisterStatus) else session.status,
        sales_total=totals['sales_total'],
        sales_count=totals['sales_count'],
        cash_sales_total=totals['cash_sales_total'],
        movements=[
            CashMovementResponse(
                id=m.id,
                session_id=m.session_id,
                user_id=m.user_id,
                type=m.type.value if isinstance(m.type, MovementType) else m.type,
                amount=m.amount,
                reason=m.reason,
                notes=m.notes,
                created_at=m.created_at,
            )
            for m in session.movements
        ],
    )


# ─── Cash Register CRUD ───────────────────────────────────────────────

@router.get("/cash-registers", response_model=List[CashRegisterResponse])
async def get_registers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "read")),
):
    return db.query(CashRegister).filter(CashRegister.is_active == True).all()


@router.post("/cash-registers", response_model=CashRegisterResponse)
async def create_register(
    data: CashRegisterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "create")),
):
    if data.warehouse_id:
        existing = db.query(CashRegister).filter(
            CashRegister.warehouse_id == data.warehouse_id,
            CashRegister.is_active == True,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una caja activa para este almacen.",
            )
    
    register = CashRegister(
        name=data.name,
        warehouse_id=data.warehouse_id,
    )
    db.add(register)
    db.commit()
    db.refresh(register)
    return register


@router.put("/cash-registers/{register_id}", response_model=CashRegisterResponse)
async def update_register(
    register_id: int,
    data: CashRegisterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "update")),
):
    register = db.query(CashRegister).filter(CashRegister.id == register_id).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    
    if data.name is not None:
        register.name = data.name
    if data.warehouse_id is not None:
        existing = db.query(CashRegister).filter(
            CashRegister.warehouse_id == data.warehouse_id,
            CashRegister.is_active == True,
            CashRegister.id != register_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una caja activa para este almacen.",
            )
        register.warehouse_id = data.warehouse_id
    if data.is_active is not None:
        register.is_active = data.is_active
    
    db.commit()
    db.refresh(register)
    return register


# ─── Cash Sessions ────────────────────────────────────────────────────

@router.get("/cash-sessions/current", response_model=CashSessionResponse)
async def get_current_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "read")),
):
    user_warehouse_ids = _get_user_warehouse_ids(current_user)
    
    query = db.query(CashSession).options(
        selectinload(CashSession.movements)
    ).join(
        CashRegister, CashSession.register_id == CashRegister.id
    )
    
    if user_warehouse_ids:
        query = query.filter(CashRegister.warehouse_id.in_(user_warehouse_ids))
    
    query = query.filter(CashSession.status == CashRegisterStatus.open)
    
    session = query.order_by(CashSession.opened_at.desc()).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="No hay sesión de caja abierta")
    
    return _enrich_session_response(db, session)


@router.get("/cash-sessions/open", response_model=List[CashSessionResponse])
async def get_open_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "read")),
):
    user_warehouse_ids = _get_user_warehouse_ids(current_user)

    query = db.query(CashSession).options(
        selectinload(CashSession.movements)
    ).join(
        CashRegister, CashSession.register_id == CashRegister.id
    ).filter(
        CashSession.status == CashRegisterStatus.open
    )

    if user_warehouse_ids:
        query = query.filter(CashRegister.warehouse_id.in_(user_warehouse_ids))

    sessions = query.order_by(CashSession.opened_at.desc()).all()

    return [_enrich_session_response(db, s) for s in sessions]


@router.post("/cash-sessions", response_model=CashSessionResponse)
async def open_session(
    data: CashSessionOpen,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "create")),
):
    register = db.query(CashRegister).filter(CashRegister.id == data.register_id).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    
    user_warehouse_ids = _get_user_warehouse_ids(current_user)
    if user_warehouse_ids and register.warehouse_id not in user_warehouse_ids:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para abrir esta caja. Solo puedes abrir cajas de tus almacenes asignados.",
        )
    
    if register.warehouse_id:
        existing = _get_open_session_for_warehouse(db, register.warehouse_id)
        if existing:
            wh = db.query(Warehouse).filter(Warehouse.id == register.warehouse_id).first()
            wh_name = wh.name if wh else f"almacen #{register.warehouse_id}"
            raise HTTPException(
                status_code=400,
                detail=f"Ya hay una caja abierta en {wh_name}. Debes cerrarla antes de abrir otra.",
            )
    
    session = CashSession(
        register_id=data.register_id,
        user_id=current_user.id,
        opening_amount=data.opening_amount,
        opening_notes=data.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return _enrich_session_response(db, session)


@router.post("/cash-sessions/{session_id}/close", response_model=CashSessionResponse)
async def close_session(
    session_id: int,
    data: CashSessionClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "update")),
):
    session = db.query(CashSession).options(
        selectinload(CashSession.movements)
    ).filter(CashSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    if session.status != CashRegisterStatus.open:
        raise HTTPException(status_code=400, detail="La sesión ya está cerrada")
    
    totals = _compute_session_totals(db, session)
    
    session.closing_amount = data.closing_amount
    session.expected_amount = totals['expected_amount']
    session.discrepancy = data.closing_amount - totals['expected_amount']
    session.closing_notes = data.notes
    session.closed_at = datetime.utcnow()
    session.closed_by_user_id = current_user.id
    session.status = CashRegisterStatus.closed
    
    db.commit()
    db.refresh(session)
    
    return _enrich_session_response(db, session)


@router.get("/cash-sessions", response_model=List[CashSessionResponse])
async def get_session_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "read")),
):
    user_warehouse_ids = _get_user_warehouse_ids(current_user)
    
    query = db.query(CashSession).options(
        selectinload(CashSession.movements)
    ).join(
        CashRegister, CashSession.register_id == CashRegister.id
    )
    
    if user_warehouse_ids and current_user.role and current_user.role.name != "admin":
        query = query.filter(CashRegister.warehouse_id.in_(user_warehouse_ids))
    
    query = query.order_by(CashSession.opened_at.desc())
    
    sessions = query.offset(skip).limit(limit).all()
    
    return [_enrich_session_response(db, s) for s in sessions]


@router.get("/cash-sessions/{session_id}/summary", response_model=CashSessionSummary)
async def get_session_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "read")),
):
    session = db.query(CashSession).options(
        selectinload(CashSession.movements)
    ).filter(CashSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    totals = _compute_session_totals(db, session)
    
    return CashSessionSummary(
        session=_enrich_session_response(db, session),
        sales_by_payment=totals['sales_by_payment'],
        total_movements_in=totals['total_movements_in'],
        total_movements_out=totals['total_movements_out'],
    )


@router.get("/cash-sessions/warehouse-summary", response_model=List[WarehouseCajaSummary])
async def get_warehouse_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).all()
    
    results = []
    for wh in warehouses:
        register = db.query(CashRegister).filter(
            CashRegister.warehouse_id == wh.id,
            CashRegister.is_active == True,
        ).first()
        
        session = None
        if register:
            session = db.query(CashSession).filter(
                CashSession.register_id == register.id,
                CashSession.status == CashRegisterStatus.open,
            ).order_by(CashSession.opened_at.desc()).first()
        
        results.append(WarehouseCajaSummary(
            warehouse_id=wh.id,
            warehouse_name=wh.name,
            register_id=register.id if register else None,
            register_name=register.name if register else None,
            session=_enrich_session_response(db, session) if session else None,
        ))
    
    return results


# ─── Cash Movements ───────────────────────────────────────────────────

@router.post("/cash-movements", response_model=CashMovementResponse)
async def add_movement(
    data: CashMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "create")),
):
    user_warehouse_ids = _get_user_warehouse_ids(current_user)
    
    session = None
    if data.session_id:
        session = db.query(CashSession).options(
            selectinload(CashSession.movements)
        ).filter(
            CashSession.id == data.session_id,
            CashSession.status == CashRegisterStatus.open,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Sesión de caja no encontrada o no está abierta.")
    else:
        query = db.query(CashSession).join(
            CashRegister, CashSession.register_id == CashRegister.id
        ).filter(CashSession.status == CashRegisterStatus.open)
        
        if user_warehouse_ids:
            query = query.filter(CashRegister.warehouse_id.in_(user_warehouse_ids))
        
        session = query.first()
    
    if not session:
        raise HTTPException(
            status_code=400,
            detail="No hay sesión de caja abierta. Debes abrir una caja antes de registrar movimientos.",
        )
    
    if data.type not in ['ingreso', 'egreso']:
        raise HTTPException(status_code=400, detail="Tipo de movimiento inválido")
    
    movement = CashMovement(
        session_id=session.id,
        user_id=current_user.id,
        type=MovementType(data.type),
        amount=data.amount,
        reason=data.reason,
        notes=data.notes,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    
    return CashMovementResponse(
        id=movement.id,
        session_id=movement.session_id,
        user_id=movement.user_id,
        type=movement.type.value,
        amount=movement.amount,
        reason=movement.reason,
        notes=movement.notes,
        created_at=movement.created_at,
    )


@router.get("/cash-movements", response_model=List[CashMovementResponse])
async def get_movements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cash_register", "read")),
):
    user_warehouse_ids = _get_user_warehouse_ids(current_user)
    
    query = db.query(CashSession).join(
        CashRegister, CashSession.register_id == CashRegister.id
    ).filter(CashSession.status == CashRegisterStatus.open)
    
    if user_warehouse_ids:
        query = query.filter(CashRegister.warehouse_id.in_(user_warehouse_ids))
    
    sessions = query.all()
    
    if not sessions:
        return []
    
    session_ids = [s.id for s in sessions]
    
    # Build warehouse name map: session_id -> warehouse_name
    wh_map = {}
    for s in sessions:
        register = db.query(CashRegister).filter(CashRegister.id == s.register_id).first()
        if register and register.warehouse_id:
            wh = db.query(Warehouse).filter(Warehouse.id == register.warehouse_id).first()
            wh_map[s.id] = wh.name if wh else None
    
    movements = db.query(CashMovement).filter(
        CashMovement.session_id.in_(session_ids)
    ).order_by(CashMovement.created_at.desc()).all()
    
    return [
        CashMovementResponse(
            id=m.id,
            session_id=m.session_id,
            user_id=m.user_id,
            type=m.type.value if isinstance(m.type, MovementType) else m.type,
            amount=m.amount,
            reason=m.reason,
            notes=m.notes,
            created_at=m.created_at,
            warehouse_name=wh_map.get(m.session_id),
        )
        for m in movements
    ]
