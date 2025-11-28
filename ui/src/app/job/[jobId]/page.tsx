import { JobDashboard } from "../../newdocument/page";

type JobPageProps = {
  params: {
    jobId: string;
  };
};

export default function JobPage({ params }: JobPageProps) {
  const jobId = decodeURIComponent(params.jobId);
  return <JobDashboard initialJobId={jobId} />;
}
