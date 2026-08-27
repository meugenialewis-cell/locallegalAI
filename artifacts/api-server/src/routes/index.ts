import { Router, type IRouter } from "express";
import healthRouter from "./health";
import legalAgentRouter from "./legal-agent";

const router: IRouter = Router();

router.use(healthRouter);
router.use(legalAgentRouter);

export default router;
